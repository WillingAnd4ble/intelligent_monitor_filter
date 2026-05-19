"""
Integration test for hybrid RRF retrieval against a real Postgres+pgvector
container — NOT a mock.

Why this exists:
  tests/test_retrieval.py::TestRRFScoreFormula tests a Python reimplementation
  of the RRF formula, not the production SQL in app/db/retrieval.py. If the
  SQL ever drifts from the spec (e.g. multiplies instead of adds the two
  reciprocals, drops the k offset, or reverses rank direction), those unit
  tests stay green because they only know about the Python copy.

  This file closes that gap by:
    1. Spinning up `pgvector/pgvector:pg16` via testcontainers.
    2. Creating the `papers` table (id, title, abstract, embedding vector(768),
       search_vector tsvector, ...) matching the production schema.
    3. Seeding 4 controlled papers chosen so that the rank order under correct
       RRF is unambiguous and different from what max() or multiplication would
       produce.
    4. Calling the real perform_hybrid_rrf_search and asserting ordering.

Test data layout:
  A: matches BOTH legs (embedding identical to query + abstract contains "agent")
  B: semantic only       (embedding close to query, no "agent" in text)
  C: lexical only        (embedding orthogonal to query, abstract contains "agent")
  D: matches NEITHER     (NULL embedding, no "agent" in text)

Expected RRF ordering with rrf_k_semantic=30, rrf_k_lexical=60, limit=50:
  A: 1/(30+1) + 1/(60+rank_lex_A) ≈ 0.049  → must be first
  C: 1/(30+3) + 1/(60+rank_lex_C) ≈ 0.046  → must beat B
  B: 1/(30+2) + 0                ≈ 0.031
  D: excluded by `WHERE ss.id IS NOT NULL OR ls.id IS NOT NULL`

The C > B assertion is the key formula-shape sentinel: if the SQL used max()
or multiplication, B (better single semantic rank) would win. The fact that C
wins proves the production SQL really does sum the two reciprocal-rank terms.

Skipped automatically when Docker isn't available. Run explicitly with:
    pytest -m integration tests/test_retrieval_integration.py
"""

import subprocess

import pytest
# Import from the submodule to bypass conftest's MagicMock-on-the-package patch.
# (conftest patches sqlalchemy.ext.asyncio.create_async_engine because the
# default unit test environment has no asyncpg; here we DO have asyncpg and
# need the real factory.)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy.ext.asyncio.engine import create_async_engine

pytestmark = pytest.mark.integration


def _docker_available() -> bool:
    try:
        r = subprocess.run(["docker", "version"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Container + schema fixture (module scope — one container per test module)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pgvector_url():
    """Start pgvector/pgvector:pg16 once per module, yield an asyncpg URL."""
    if not _docker_available():
        pytest.skip("Docker not available — integration tests require testcontainers")
    from testcontainers.postgres import PostgresContainer
    with PostgresContainer(
        image="pgvector/pgvector:pg16",
        driver="asyncpg",
    ) as pg:
        url = pg.get_connection_url()
        # Defensive: some testcontainers builds ignore driver= and still
        # return a psycopg2 URL. Force asyncpg either way.
        if "+psycopg2" in url:
            url = url.replace("+psycopg2", "+asyncpg")
        elif "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://")
        yield url


# ---------------------------------------------------------------------------
# Per-test session + seed (function scope — fresh schema/seed per test)
# ---------------------------------------------------------------------------

def _vec_768(pos0: float, pos1: float) -> str:
    """Build a pgvector literal for a 768-d vector with only pos0/pos1 nonzero."""
    tail = ",".join(["0"] * 766)
    return f"[{pos0},{pos1},{tail}]"


SEED_PAPERS = [
    # (id, title, abstract, embedding-or-None)
    ("A",
     "Multi-agent coordination in LLMs",
     "Cooperating agent teams plan via natural-language messages.",
     _vec_768(1.0, 0.0)),
    ("B",
     "Quantum entanglement bounds",
     "We derive new bounds for entanglement entropy in lattice systems.",
     _vec_768(0.95, 0.05)),
    ("C",
     "Robotic agent control loops",
     "We describe agent-based control for industrial robots.",
     _vec_768(0.0, 1.0)),
    ("D",
     "Crop rotation in Scandinavia",
     "Twenty-year field trial review of rotation in Sweden and Norway.",
     None),  # NULL embedding → excluded from semantic CTE
]


@pytest.fixture
async def seeded_session(pgvector_url):
    """Fresh engine + schema + 4-paper seed per test. Disposed on teardown."""
    engine = create_async_engine(pgvector_url, future=True)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(text("DROP TABLE IF EXISTS papers CASCADE"))
            await conn.execute(text("""
                CREATE TABLE papers (
                    id            TEXT PRIMARY KEY,
                    title         TEXT NOT NULL,
                    abstract      TEXT NOT NULL,
                    authors       JSONB,
                    embedding     vector(768),
                    search_vector tsvector,
                    pdf_url       TEXT,
                    source_url    TEXT,
                    published_at  TIMESTAMPTZ
                )
            """))

            for pid, title, abstract, embedding in SEED_PAPERS:
                if embedding is None:
                    await conn.execute(text("""
                        INSERT INTO papers (id, title, abstract, embedding, search_vector)
                        VALUES (:id, :title, :abstract, NULL,
                                to_tsvector('english', :title || ' ' || :abstract))
                    """), {"id": pid, "title": title, "abstract": abstract})
                else:
                    await conn.execute(text("""
                        INSERT INTO papers (id, title, abstract, embedding, search_vector)
                        VALUES (:id, :title, :abstract,
                                CAST(:embedding AS vector),
                                to_tsvector('english', :title || ' ' || :abstract))
                    """), {
                        "id": pid, "title": title, "abstract": abstract,
                        "embedding": embedding,
                    })

        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            yield session
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Query parameters — same query reused across all three tests
# ---------------------------------------------------------------------------

QUERY_TEXT = "agent"
QUERY_EMBEDDING = [1.0, 0.0] + [0.0] * 766  # identical to Paper A


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_paper_matching_both_legs_ranks_first(seeded_session):
    """A (semantic #1 + lexical match) must beat all others."""
    from app.db.retrieval import perform_hybrid_rrf_search
    results = await perform_hybrid_rrf_search(
        session=seeded_session,
        query_text=QUERY_TEXT,
        query_embedding=QUERY_EMBEDDING,
        limit=50,
    )
    assert len(results) > 0, "No results returned at all — SQL or seed is broken"
    assert results[0]["id"] == "A", (
        f"Expected A (both legs match) first; "
        f"got order {[r['id'] for r in results]}"
    )


async def test_rrf_is_additive_two_weak_legs_beat_one_strong(seeded_session):
    """C (rank_sem=3 + rank_lex≈1) must score above B (rank_sem=2, no lex match).

    This is the formula-shape sentinel:
      - If SQL used max(reciprocal_sem, reciprocal_lex): B's better semantic
        rank (1/32 ≈ 0.0313) would beat C's worse one (1/33 ≈ 0.0303).
      - If SQL multiplied instead of added: C with rank_lex≠NULL multiplied by
        a worse rank_sem could land anywhere — the ordering would be unstable.
      - Only the correct additive form gives C > B reliably.
    """
    from app.db.retrieval import perform_hybrid_rrf_search
    results = await perform_hybrid_rrf_search(
        session=seeded_session,
        query_text=QUERY_TEXT,
        query_embedding=QUERY_EMBEDDING,
        limit=50,
    )
    by_id = {r["id"]: r["rrf_score"] for r in results}
    assert "B" in by_id, f"B missing from results: {list(by_id)}"
    assert "C" in by_id, f"C missing from results: {list(by_id)}"
    assert by_id["C"] > by_id["B"], (
        f"RRF additivity violated: B={by_id['B']:.6f} >= C={by_id['C']:.6f}. "
        "Two weaker legs should outweigh one stronger leg under sum-of-reciprocals."
    )


async def test_paper_matching_neither_leg_is_excluded(seeded_session):
    """D (NULL embedding + no 'agent' in text) must NOT appear at all."""
    from app.db.retrieval import perform_hybrid_rrf_search
    results = await perform_hybrid_rrf_search(
        session=seeded_session,
        query_text=QUERY_TEXT,
        query_embedding=QUERY_EMBEDDING,
        limit=50,
    )
    ids = [r["id"] for r in results]
    assert "D" not in ids, (
        f"D should be excluded by `WHERE ss.id IS NOT NULL OR ls.id IS NOT NULL`; "
        f"got results: {ids}"
    )


@pytest.mark.parametrize("k_sem, k_lex, expected_top3", [
    pytest.param(30, 60, ["A", "C", "B"], id="default-semantic-biased"),
    pytest.param(60, 60, ["A", "C", "B"], id="symmetric-k"),
    pytest.param(60, 30, ["A", "C", "B"], id="lexical-biased"),
    pytest.param(1,  20, ["A", "B", "C"], id="extreme-semantic-flips-order"),
])
async def test_rrf_respects_k_configuration(seeded_session, k_sem, k_lex, expected_top3):
    """Ordering changes with k_sem/k_lex — proves the parameters actually reach SQL bind
    params and aren't hardcoded inside the query.

    First three cases prove the additive form is robust to k variation (A > C > B holds
    even as absolute scores shift). The fourth case uses k_sem=1 (huge semantic weight),
    which mathematically flips B and C (B keeps its better semantic rank, C loses its
    two-leg advantage). If anyone ever hardcoded k values in the SQL, only this case
    would fail — making it the parameter-plumbing sentinel.

    Score table for reference (assuming A=lex#1, C=lex#2):
        k_sem  k_lex   A          B          C          Order
        30     60      0.0487     0.0313     0.0464     A > C > B
        60     60      0.0328     0.0161     0.0320     A > C > B
        60     30      0.0487     0.0161     0.0472     A > C > B
        1      20      0.5476     0.3333     0.2955     A > B > C   ← flip
    """
    from app.db.retrieval import perform_hybrid_rrf_search
    results = await perform_hybrid_rrf_search(
        session=seeded_session,
        query_text=QUERY_TEXT,
        query_embedding=QUERY_EMBEDDING,
        limit=50,
        rrf_k_semantic=k_sem,
        rrf_k_lexical=k_lex,
    )
    top3 = [r["id"] for r in results[:3]]
    assert top3 == expected_top3, (
        f"k_sem={k_sem}, k_lex={k_lex}: expected {expected_top3}, got {top3}; "
        f"full scores: {[(r['id'], round(r['rrf_score'], 6)) for r in results]}"
    )
