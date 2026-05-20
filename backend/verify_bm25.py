"""
Standalone check that the BM25 + RRF hybrid retrieval works against the LIVE
database (the real 235-paper corpus), not synthetic test data.

Run from the backend/ directory:
    py verify_bm25.py

What it does:
  1. Picks a real paper and uses its SPECTER2 embedding as the query vector
     (so the semantic leg is meaningful, not all-zeros).
  2. Runs perform_hybrid_rrf_search with a lexical query alongside.
  3. Prints the RRF-ranked results.

If you see ~10 papers come back with descending rrf_score and every score > 0,
the ts_rank_cd -> rank_bm25 migration works end to end against your real data.

This is a throwaway dev script — safe to delete after checking.
"""

import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession, create_async_engine

from app.db.retrieval import perform_hybrid_rrf_search

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5433/arxiv_intel",
)
QUERY_TEXT = "multi-agent reinforcement learning"


async def main() -> None:
    engine = create_async_engine(DB_URL)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Session() as session:
            # Use a real paper's embedding as the query vector.
            seed = (await session.execute(text(
                "SELECT id, title, embedding FROM papers "
                "WHERE embedding IS NOT NULL LIMIT 1"
            ))).mappings().first()
            if seed is None:
                print("No papers with embeddings in the DB — nothing to verify.")
                return

            emb_raw = seed["embedding"]
            if isinstance(emb_raw, str):
                embedding = [float(x) for x in emb_raw.strip("[]").split(",") if x]
            else:
                embedding = [float(x) for x in emb_raw]

            print(f"Query text   : {QUERY_TEXT!r}")
            print(f"Query vector : SPECTER2 embedding of seed paper {seed['id']}")
            print(f"               ({seed['title'][:60]})")
            print(f"Embedding dim: {len(embedding)}")
            print("-" * 80)

            results = await perform_hybrid_rrf_search(
                session=session,
                query_text=QUERY_TEXT,
                query_embedding=embedding,
                limit=10,
            )

            if not results:
                print("No results returned — check the corpus / query.")
                return

            print(f"{'#':>2}  {'rrf_score':>10}  {'paper id':<16}  title")
            print("-" * 80)
            for i, r in enumerate(results, start=1):
                print(f"{i:>2}  {r['rrf_score']:>10.6f}  {r['id']:<16}  "
                      f"{r['title'][:46]}")
            print("-" * 80)

            scores = [r["rrf_score"] for r in results]
            descending = all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))
            all_positive = all(s > 0 for s in scores)
            print(f"Results returned : {len(results)}")
            print(f"Scores descending: {descending}")
            print(f"All scores > 0   : {all_positive}")
            if descending and all_positive:
                print()
                print("OK — BM25 + RRF hybrid retrieval works against the live DB.")
            else:
                print()
                print("UNEXPECTED — inspect the ranking above.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
