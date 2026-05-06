"""Candidate retrievers: BM25, SPECTER2, RRF.

Each returns a list of CandidatePaper objects pulled from the prod papers table.
SPECTER2 embedding for the goal is computed via Modal GPU on demand.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal

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
    url = os.environ.get("BENCHMARK_DB_URL")
    if not url:
        raise RuntimeError(
            "BENCHMARK_DB_URL is unset. Copy testing/.env.benchmark.example "
            "to testing/.env.benchmark and load it before running."
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


async def pull_bm25(session: AsyncSession, lexical_query: str, k: int = 30) -> List[CandidatePaper]:
    stmt = text("""
        SELECT p.id, p.title, p.abstract, p.authors, p.pdf_url, p.source_url, p.published_at,
               ts_rank_cd(p.search_vector, websearch_to_tsquery('english', :q)) AS lex_score,
               EXISTS (
                 SELECT 1 FROM user_papers up
                 WHERE up.paper_id = p.id AND up.extracted_markdown IS NOT NULL
               ) AS has_md
        FROM papers p
        WHERE p.search_vector @@ websearch_to_tsquery('english', :q)
        ORDER BY lex_score DESC
        LIMIT :k
    """)
    rows = (await session.execute(stmt, {"q": lexical_query, "k": k})).mappings().fetchall()
    return [
        CandidatePaper(
            paper_id=r["id"], title=r["title"], abstract=r["abstract"],
            authors=list(r["authors"] or []), pdf_url=r["pdf_url"],
            rrf_rank=i + 1, rrf_score=float(r["lex_score"]),
            has_extracted_markdown=bool(r["has_md"]),
        )
        for i, r in enumerate(rows)
    ]


async def pull_specter2(session: AsyncSession, goal_embedding: List[float], k: int = 30) -> List[CandidatePaper]:
    vector_str = f"[{','.join(map(str, goal_embedding))}]"
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
    rows = (await session.execute(stmt, {"emb": vector_str, "k": k})).mappings().fetchall()
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
                   k: int = 30, k_semantic: int = 30, k_lexical: int = 60) -> List[CandidatePaper]:
    rows = await perform_hybrid_rrf_search(
        session=session,
        query_text=lexical_query,
        query_embedding=goal_embedding,
        limit=k,
        rrf_k_semantic=k_semantic,
        rrf_k_lexical=k_lexical,
    )
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
                        k: int = 30) -> CandidatesFile:
    engine = _engine()
    factory = _session_factory(engine)
    async with factory() as session:
        if retriever == "bm25":
            papers = await pull_bm25(session, lexical_query, k=k)
            rrf_params = None
        elif retriever == "specter2":
            papers = await pull_specter2(session, goal_embedding, k=k)
            rrf_params = None
        else:
            papers = await pull_rrf(session, lexical_query, goal_embedding, k=k)
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
