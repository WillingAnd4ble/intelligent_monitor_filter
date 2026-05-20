"""
Hybrid retrieval combining SPECTER2 semantic similarity (via pgvector) and
BM25 lexical relevance, fused via Reciprocal Rank Fusion (RRF).

Lexical ranking previously used PostgreSQL's `ts_rank_cd` (cover density)
function. This module now uses Okapi BM25 from `rank_bm25`, applied in Python
over candidates that pass the tsvector @@ tsquery boolean filter — matching
the algorithm the thesis describes (Robertson & Zaragoza, 2009) with the
standard parameters k1=1.5, b=0.75.

Architecture (hybrid SQL + Python):
  - Semantic leg: pgvector `<=>` cosine distance in SQL, index-backed top-N
    selection. Python only assigns rank numbers via enumeration.
  - Lexical leg:  tsvector boolean filter in SQL (GIN-index-backed) selects
    keyword-matching candidates; BM25Okapi computes per-document relevance
    scores in Python over those candidates.
  - RRF fusion:   combined in Python from the two rank dicts using the
    standard reciprocal-rank-fusion formula 1/(k + rank).

PostgreSQL still does the expensive work (vector similarity, full-text
boolean filter). Python only ranks and combines, both O(N) operations
over the candidate set (typically <100 papers for narrow queries).
"""

import re
from typing import Any, Dict, List

from nltk.stem.snowball import SnowballStemmer
from rank_bm25 import BM25Okapi
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Module-level Snowball stemmer (English) — reused across calls. Matches the
# stemming PostgreSQL applies via to_tsvector('english', ...), so the same
# query word matches the same document tokens between the lexical filter
# (SQL) and the BM25 scoring (Python).
_STEMMER = SnowballStemmer("english")

# Tokens for BM25: lowercase, alphanumeric only, then English-stemmed.
# Mirrors PostgreSQL's to_tsvector('english', ...) lexical normalization
# closely enough that BM25 over Python-side tokens scores the same documents
# the tsvector filter selected.
_TOKEN_RE = re.compile(r"\b[a-z0-9]+\b")


def _tokenize(value: str) -> List[str]:
    """Lowercase + extract alphanumeric tokens + Snowball-stem each."""
    if not value:
        return []
    return [_STEMMER.stem(t) for t in _TOKEN_RE.findall(value.lower())]


async def perform_hybrid_rrf_search(
    session: AsyncSession,
    query_text: str,
    query_embedding: List[float],
    limit: int = 50,
    rrf_k_semantic: int = 30,
    rrf_k_lexical: int = 60,
) -> List[Dict[str, Any]]:
    """
    Hybrid retrieval: SPECTER2 + pgvector cosine (semantic) and BM25Okapi
    (lexical) combined via Reciprocal Rank Fusion.

    Args:
        session:        Async SQLAlchemy session.
        query_text:     Lexical query (typically the GoalDistiller's
                        `lexical_query` — a short keyword sequence).
        query_embedding: 768-d SPECTER2 vector (the user's `goal_embedding`).
        limit:          Maximum number of results to return.
        rrf_k_semantic: RRF dampening constant for the semantic leg (smaller
                        = larger semantic weight). Default 30 per the
                        thesis's semantic-biased fusion design.
        rrf_k_lexical:  RRF dampening constant for the lexical leg. Default
                        60 (roughly half the semantic weight).

    Returns:
        List of paper dicts sorted by rrf_score descending, capped at
        `limit`. Each dict contains: id, title, abstract, authors, pdf_url,
        source_url, published_at, rrf_score.
    """

    # ----- Semantic leg ---------------------------------------------------
    # pgvector cosine distance, ORDER BY <=>, LIMIT N. The index does the
    # heavy lifting; Python only converts position-in-result to rank number.
    vector_str = f"[{','.join(map(str, query_embedding))}]"
    sem_result = await session.execute(
        text("""
            SELECT id, title, abstract, authors, pdf_url, source_url, published_at
            FROM papers
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:embedding_val AS vector)
            LIMIT :limit
        """),
        {"embedding_val": vector_str, "limit": limit},
    )
    semantic_rows = [dict(r) for r in sem_result.mappings().fetchall()]
    semantic_ranks = {row["id"]: i for i, row in enumerate(semantic_rows, start=1)}

    # ----- Lexical leg ----------------------------------------------------
    # tsvector @@ tsquery as a boolean candidate filter only. Real scoring
    # happens via BM25Okapi in Python below. ORDER BY id ASC for stable
    # candidate ordering when multiple documents tie on BM25 score.
    lex_result = await session.execute(
        text("""
            SELECT id, title, abstract, authors, pdf_url, source_url, published_at
            FROM papers
            WHERE search_vector @@ websearch_to_tsquery('english', :query_text)
            ORDER BY id ASC
        """),
        {"query_text": query_text},
    )
    lexical_rows = [dict(r) for r in lex_result.mappings().fetchall()]

    lexical_ranks: Dict[Any, int] = {}
    if lexical_rows:
        # Build BM25 corpus from title + abstract per paper.
        # k1=1.5: term-frequency saturation point (Robertson & Zaragoza 2009).
        # b=0.75: document-length normalization weight.
        corpus = [
            _tokenize((row.get("title") or "") + " " + (row.get("abstract") or ""))
            for row in lexical_rows
        ]
        bm25 = BM25Okapi(corpus, k1=1.5, b=0.75)
        scores = bm25.get_scores(_tokenize(query_text))
        # Higher BM25 score = better match → lower rank number.
        ranked = sorted(zip(lexical_rows, scores), key=lambda x: x[1], reverse=True)
        lexical_ranks = {row["id"]: i for i, (row, _) in enumerate(ranked, start=1)}

    # ----- RRF fusion -----------------------------------------------------
    # Standard reciprocal-rank-fusion: per paper, sum 1/(k+rank) over
    # whichever leg(s) it appears in. Papers excluded from both legs are
    # not in `all_papers` and therefore not in the output (matches the
    # `WHERE ss.id IS NOT NULL OR ls.id IS NOT NULL` semantics of the
    # previous SQL outer-join version).
    all_papers: Dict[Any, Dict[str, Any]] = {}
    for row in semantic_rows:
        all_papers[row["id"]] = row
    for row in lexical_rows:
        all_papers.setdefault(row["id"], row)

    for pid, paper in all_papers.items():
        score = 0.0
        if pid in semantic_ranks:
            score += 1.0 / (rrf_k_semantic + semantic_ranks[pid])
        if pid in lexical_ranks:
            score += 1.0 / (rrf_k_lexical + lexical_ranks[pid])
        paper["rrf_score"] = score

    return sorted(
        all_papers.values(), key=lambda p: p["rrf_score"], reverse=True
    )[:limit]
