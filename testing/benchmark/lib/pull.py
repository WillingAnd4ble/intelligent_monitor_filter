"""Candidate retrievers: BM25, SPECTER2, RRF.

Each returns a list of CandidatePaper objects pulled from the prod papers table.
SPECTER2 embedding for the goal is computed via Modal GPU on demand.
"""

import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Allow importing from ../backend
_BACKEND = Path(__file__).resolve().parents[3] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.db.retrieval import perform_hybrid_rrf_search  # type: ignore
from app.worker.modal_client import specter2_embed_batch  # type: ignore

from benchmark.lib import paths
from benchmark.lib.schemas import CandidatePaper, CandidatesFile


def _engine():
    """Pick the DB URL: prefer BENCHMARK_DB_URL, fall back to DATABASE_URL.

    Phase 1 reuses the backend's prod connection. Phase 2 will introduce a
    dedicated readonly_user; until then, BENCHMARK_DB_URL stays optional.
    The placeholder value from .env.benchmark.example (containing
    ``readonly_user:password``) is treated as unset.
    """
    url = os.environ.get("BENCHMARK_DB_URL")
    if not url or "readonly_user:password" in url:
        url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Neither BENCHMARK_DB_URL nor DATABASE_URL is set. "
            "Ensure backend/.env has DATABASE_URL or set BENCHMARK_DB_URL "
            "in testing/.env.benchmark."
        )
    return create_async_engine(url, future=True, pool_pre_ping=True)


def _session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


async def smoke_test_db_access() -> int:
    """Run a SELECT 1 + count papers. Fails fast with clear message if DB unreachable."""
    engine = _engine()
    factory = _session_factory(engine)
    async with factory() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM papers"))
        return result.scalar_one()


async def embed_goal(raw_goal: str, goal_id: str) -> List[float]:
    """Compute SPECTER2 embedding for the goal text. Used for SPECTER2 + RRF retrievers.

    The backend SPECTER2 wrapper expects a list of {"title": ..., "abstract": ...}
    dicts. Synthesize one with the goal text in the abstract slot.
    """
    pairs = [{"title": goal_id, "abstract": raw_goal}]
    embeddings = await specter2_embed_batch(pairs)
    return embeddings[0]


def _or_query(lexical_query: str) -> str:
    """Build a to_tsquery OR-string from free-form terms, e.g.
    'llm hybrid attack' -> 'llm | hybrid | attack'. Drops words shorter
    than 3 chars and dedupes."""
    seen: list[str] = []
    for tok in re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", lexical_query):
        t = tok.lower()
        if t not in seen:
            seen.append(t)
    return " | ".join(seen)


async def _bm25_strict(session: AsyncSession, lexical_query: str, k: int,
                       paper_ids: Optional[List[str]]):
    base = """
        SELECT p.id, p.title, p.abstract, p.authors, p.pdf_url, p.source_url, p.published_at,
               ts_rank_cd(p.search_vector, websearch_to_tsquery('english', :q)) AS lex_score,
               EXISTS (
                 SELECT 1 FROM user_papers up
                 WHERE up.paper_id = p.id AND up.extracted_markdown IS NOT NULL
               ) AS has_md
        FROM papers p
        WHERE p.search_vector @@ websearch_to_tsquery('english', :q)
          {id_filter}
        ORDER BY lex_score DESC
        LIMIT :k
    """
    if paper_ids is None:
        stmt = text(base.format(id_filter=""))
        params = {"q": lexical_query, "k": k}
    else:
        stmt = text(base.format(id_filter="AND p.id = ANY(:ids)"))
        params = {"q": lexical_query, "k": k, "ids": list(paper_ids)}
    return (await session.execute(stmt, params)).mappings().fetchall()


async def _bm25_loose(session: AsyncSession, or_query: str, k: int,
                      paper_ids: Optional[List[str]]):
    base = """
        SELECT p.id, p.title, p.abstract, p.authors, p.pdf_url, p.source_url, p.published_at,
               ts_rank_cd(p.search_vector, to_tsquery('english', :q)) AS lex_score,
               EXISTS (
                 SELECT 1 FROM user_papers up
                 WHERE up.paper_id = p.id AND up.extracted_markdown IS NOT NULL
               ) AS has_md
        FROM papers p
        WHERE p.search_vector @@ to_tsquery('english', :q)
          {id_filter}
        ORDER BY lex_score DESC
        LIMIT :k
    """
    if paper_ids is None:
        stmt = text(base.format(id_filter=""))
        params = {"q": or_query, "k": k}
    else:
        stmt = text(base.format(id_filter="AND p.id = ANY(:ids)"))
        params = {"q": or_query, "k": k, "ids": list(paper_ids)}
    return (await session.execute(stmt, params)).mappings().fetchall()


async def pull_bm25(session: AsyncSession, lexical_query: str, k: int = 30,
                    paper_ids: Optional[List[str]] = None) -> List[CandidatePaper]:
    """BM25 retrieval. Tries strict AND first; falls back to OR over terms
    if zero rows match. The fallback prevents empty result sets on small
    corpora while still ranking the most-overlapping papers highest.
    """
    rows = await _bm25_strict(session, lexical_query, k, paper_ids)
    if not rows:
        or_q = _or_query(lexical_query)
        if or_q:
            rows = await _bm25_loose(session, or_q, k, paper_ids)
    return [
        CandidatePaper(
            paper_id=r["id"], title=r["title"], abstract=r["abstract"],
            authors=list(r["authors"] or []), pdf_url=r["pdf_url"],
            rrf_rank=i + 1, rrf_score=float(r["lex_score"]),
            has_extracted_markdown=bool(r["has_md"]),
        )
        for i, r in enumerate(rows)
    ]


async def pull_specter2(session: AsyncSession, goal_embedding: List[float], k: int = 30,
                        paper_ids: Optional[List[str]] = None) -> List[CandidatePaper]:
    vector_str = f"[{','.join(map(str, goal_embedding))}]"
    if paper_ids is None:
        stmt = text("""
            SELECT p.id, p.title, p.abstract, p.authors, p.pdf_url, p.source_url, p.published_at,
                   1 - (p.embedding <=> CAST(:emb AS vector)) AS sim,
                   EXISTS (
                     SELECT 1 FROM user_papers up
                     WHERE up.paper_id = p.id AND up.extracted_markdown IS NOT NULL
                   ) AS has_md
            FROM papers p
            WHERE p.embedding IS NOT NULL
            ORDER BY p.embedding <=> CAST(:emb AS vector)
            LIMIT :k
        """)
        params = {"emb": vector_str, "k": k}
    else:
        stmt = text("""
            SELECT p.id, p.title, p.abstract, p.authors, p.pdf_url, p.source_url, p.published_at,
                   1 - (p.embedding <=> CAST(:emb AS vector)) AS sim,
                   EXISTS (
                     SELECT 1 FROM user_papers up
                     WHERE up.paper_id = p.id AND up.extracted_markdown IS NOT NULL
                   ) AS has_md
            FROM papers p
            WHERE p.embedding IS NOT NULL
              AND p.id = ANY(:ids)
            ORDER BY p.embedding <=> CAST(:emb AS vector)
            LIMIT :k
        """)
        params = {"emb": vector_str, "k": k, "ids": list(paper_ids)}
    rows = (await session.execute(stmt, params)).mappings().fetchall()
    return [
        CandidatePaper(
            paper_id=r["id"], title=r["title"], abstract=r["abstract"],
            authors=list(r["authors"] or []), pdf_url=r["pdf_url"],
            rrf_rank=i + 1, rrf_score=float(r["sim"]),
            has_extracted_markdown=bool(r["has_md"]),
        )
        for i, r in enumerate(rows)
    ]


async def pull_rrf(session: AsyncSession, lexical_query: str, goal_embedding: List[float],
                   k: int = 30, k_semantic: int = 30, k_lexical: int = 60,
                   paper_ids: Optional[List[str]] = None) -> List[CandidatePaper]:
    # If a dataset filter is in effect, ask RRF for a wider window and filter
    # locally — backend perform_hybrid_rrf_search has no id-restriction param.
    rrf_limit = max(k, len(paper_ids)) if paper_ids else k
    rows = await perform_hybrid_rrf_search(
        session=session,
        query_text=lexical_query,
        query_embedding=goal_embedding,
        limit=rrf_limit,
        rrf_k_semantic=k_semantic,
        rrf_k_lexical=k_lexical,
    )
    if paper_ids is not None:
        allow = set(paper_ids)
        rows = [r for r in rows if r["id"] in allow][:k]
    if not rows:
        return []
    ids = [r["id"] for r in rows]
    md_q = text("""
        SELECT paper_id, COUNT(*) > 0 AS has_md
        FROM user_papers
        WHERE paper_id = ANY(:ids) AND extracted_markdown IS NOT NULL
        GROUP BY paper_id
    """)
    md_rows = (await session.execute(md_q, {"ids": ids})).mappings().fetchall()
    md_set = {r["paper_id"] for r in md_rows if r["has_md"]}

    return [
        CandidatePaper(
            paper_id=r["id"], title=r["title"], abstract=r["abstract"],
            authors=list(r.get("authors") or []), pdf_url=r.get("pdf_url"),
            rrf_rank=i + 1, rrf_score=float(r["rrf_score"]),
            has_extracted_markdown=r["id"] in md_set,
        )
        for i, r in enumerate(rows)
    ]


async def pull_and_save(goal_id: str, retriever: Literal["bm25", "specter2", "rrf"],
                        lexical_query: str, goal_embedding: List[float],
                        k: int = 30,
                        paper_ids: Optional[List[str]] = None) -> CandidatesFile:
    engine = _engine()
    factory = _session_factory(engine)
    async with factory() as session:
        if retriever == "bm25":
            papers = await pull_bm25(session, lexical_query, k=k, paper_ids=paper_ids)
            rrf_params = None
        elif retriever == "specter2":
            papers = await pull_specter2(session, goal_embedding, k=k, paper_ids=paper_ids)
            rrf_params = None
        else:
            papers = await pull_rrf(session, lexical_query, goal_embedding, k=k, paper_ids=paper_ids)
            rrf_params = {"k_semantic": 30, "k_lexical": 60}

    cf = CandidatesFile(
        goal_id=goal_id, retriever=retriever, top_k=k,
        rrf_params=rrf_params, pulled_at=datetime.now(timezone.utc),
        papers=papers,
    )
    paths.ensure_subdirs()
    paths.candidates_path(goal_id, retriever).write_text(
        cf.model_dump_json(indent=2), encoding="utf-8"
    )
    return cf
