"""
Fallback search module: queries the year corpus when the daily pipeline
returns fewer than N papers.

This is designed to be imported by the backend's celery_app.py as an
additional candidate source. When trigger_agent_discovery finds < threshold
papers from the daily scrape + RRF, it calls corpus_fallback_search() to
pull more candidates from the full year of embedded papers.

Two search modes:
  1. DB mode  — queries PostgreSQL directly (after db_loader has populated it)
  2. Local mode — queries the numpy embeddings + JSONL files (no DB required)

Usage from backend:
    from year_scrape.fallback_search import corpus_fallback_search
    extra_papers = corpus_fallback_search(
        query_text="multi-agent LLM coordination",
        query_embedding=goal_embedding,  # 768-dim list
        exclude_ids=already_seen_ids,
        limit=10,
    )
"""

import json
import logging
import numpy as np
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Resolve paths relative to this file
_THIS_DIR = Path(__file__).parent
_DATA_DIR = _THIS_DIR / "data"
_PAPERS_JSONL = _DATA_DIR / "papers.jsonl"
_EMBEDDINGS_NPY = _DATA_DIR / "embeddings.npy"
_INDEX_JSON = _DATA_DIR / "index.json"


# ── Local mode (numpy cosine similarity) ─────────────────────────

def _load_local_corpus():
    """Load papers + embeddings from local files."""
    papers_by_id = {}
    with open(_PAPERS_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            p = json.loads(line)
            papers_by_id[p["paper_id"]] = p

    embeddings = np.load(_EMBEDDINGS_NPY).astype(np.float32)
    with open(_INDEX_JSON, "r") as f:
        index = json.load(f)

    return papers_by_id, embeddings, index


def _cosine_similarity_batch(query: np.ndarray, corpus: np.ndarray) -> np.ndarray:
    """Cosine similarity between a single query vector and a matrix of corpus vectors."""
    query_norm = query / (np.linalg.norm(query) + 1e-10)
    corpus_norms = corpus / (np.linalg.norm(corpus, axis=1, keepdims=True) + 1e-10)
    return corpus_norms @ query_norm


def local_search(
    query_embedding: list[float],
    exclude_ids: set[str] = None,
    limit: int = 10,
) -> list[dict]:
    """
    Search the local numpy corpus by cosine similarity.

    Returns a list of paper dicts, sorted by similarity score descending.
    Each dict includes an extra 'similarity_score' field.
    """
    exclude_ids = exclude_ids or set()

    papers_by_id, embeddings, index = _load_local_corpus()
    query = np.array(query_embedding, dtype=np.float32)

    scores = _cosine_similarity_batch(query, embeddings)

    # Build (idx, score) pairs, excluding already-seen papers
    candidates = []
    for i, pid in enumerate(index):
        if pid not in exclude_ids:
            candidates.append((i, scores[i], pid))

    # Sort by score descending
    candidates.sort(key=lambda x: x[1], reverse=True)

    results = []
    for idx, score, pid in candidates[:limit]:
        paper = papers_by_id.get(pid, {})
        results.append({
            "id": pid,
            "title": paper.get("title", ""),
            "abstract": paper.get("abstract", ""),
            "authors": paper.get("authors", []),
            "pdf_url": paper.get("pdf_url"),
            "source_url": paper.get("source_url"),
            "published_at": paper.get("published_at"),
            "similarity_score": float(score),
        })

    return results


# ── DB mode (PostgreSQL pgvector query) ──────────────────────────

async def db_search(
    session,  # AsyncSession from the backend
    query_embedding: list[float],
    exclude_ids: set[str] = None,
    limit: int = 10,
) -> list[dict]:
    """
    Search the papers table in PostgreSQL by cosine similarity.

    This queries the same DB the backend uses — works after db_loader
    has populated it with the year corpus.
    """
    from sqlalchemy import text

    exclude_ids = exclude_ids or set()
    vector_str = f"[{','.join(map(str, query_embedding))}]"

    # Base query
    query = text("""
        SELECT id, title, abstract, authors, pdf_url, source_url, published_at,
               embedding <=> CAST(:emb AS vector) AS distance
        FROM papers
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> CAST(:emb AS vector)
        LIMIT :search_limit
    """)

    result = await session.execute(query, {"emb": vector_str, "search_limit": limit + len(exclude_ids)})
    rows = result.mappings().fetchall()

    results = []
    for row in rows:
        if row["id"] in exclude_ids:
            continue
        results.append({
            "id": row["id"],
            "title": row["title"],
            "abstract": row["abstract"],
            "authors": row["authors"],
            "pdf_url": row["pdf_url"],
            "source_url": row["source_url"],
            "published_at": str(row["published_at"]) if row["published_at"] else None,
            "similarity_score": 1.0 - float(row["distance"]),  # convert distance to similarity
        })
        if len(results) >= limit:
            break

    return results


# ── Unified entry point ──────────────────────────────────────────

def corpus_fallback_search(
    query_text: str = "",
    query_embedding: Optional[list[float]] = None,
    exclude_ids: set[str] = None,
    limit: int = 10,
    mode: str = "local",
    session=None,
) -> list[dict]:
    """
    Main entry point for fallback search.

    Args:
        query_text:      For future BM25 support (not used in local mode)
        query_embedding:  768-dim SPECTER2 embedding of the user's goal
        exclude_ids:      Paper IDs already in the user's feed (skip these)
        limit:            Max papers to return
        mode:             "local" (numpy) or "db" (PostgreSQL)
        session:          AsyncSession, required for db mode

    Returns:
        List of paper dicts with similarity_score, ready for the agent pipeline.
    """
    exclude_ids = exclude_ids or set()

    if query_embedding is None:
        logger.warning("No query_embedding provided — cannot do semantic search")
        return []

    if mode == "local":
        if not _EMBEDDINGS_NPY.exists():
            logger.warning(f"No embeddings file at {_EMBEDDINGS_NPY}. Run embedder.py first.")
            return []
        return local_search(query_embedding, exclude_ids, limit)

    elif mode == "db":
        if session is None:
            raise ValueError("session is required for db mode")
        import asyncio
        return asyncio.run(db_search(session, query_embedding, exclude_ids, limit))

    else:
        raise ValueError(f"Unknown mode: {mode}. Use 'local' or 'db'.")


# ── CLI for testing ──────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test fallback search")
    parser.add_argument("--query", type=str, default="multi-agent LLM coordination")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    # Generate a rough query embedding using the first paper's embedding as proxy
    # (In production, you'd embed the query via SPECTER2)
    embeddings = np.load(_EMBEDDINGS_NPY)
    # Use a random embedding as mock query
    mock_query = embeddings[0].tolist()

    results = corpus_fallback_search(
        query_embedding=mock_query,
        limit=args.limit,
    )

    for i, r in enumerate(results):
        print(f"\n{i+1}. [{r['similarity_score']:.4f}] {r['title']}")
        print(f"   ID: {r['id']}")