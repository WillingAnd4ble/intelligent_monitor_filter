from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any

async def perform_hybrid_rrf_search(
    session: AsyncSession,
    query_text: str,
    query_embedding: List[float],
    limit: int = 50,
    rrf_k: int = 60
) -> List[Dict[str, Any]]:
    """
    Executes a high-efficiency Reciprocal Rank Fusion (RRF) query utilizing native PostgreSQL mapping.
    
    The Funnel merges:
    1. Deep Semantic vector search mapping (Cosine Distance <=> target).
    2. BM25 Lexical overlap ranking utilizing `websearch_to_tsquery`.
    
    Outputs a consolidated score neutralizing generalized limits gracefully natively avoiding massive Python allocations!
    """
    
    # We utilize strict raw text logic as RRF mapping demands deep outer joins across CTE limits 
    # operating natively bypassing the Python ORM overhead structurally!
    stmt = text("""
        WITH semantic_search AS (
            SELECT 
                id, 
                RANK() OVER (ORDER BY embedding <=> CAST(:embedding_val AS vector)) as rank_semantic
            FROM papers
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:embedding_val AS vector)
            LIMIT :limit
        ),
        lexical_search AS (
            SELECT 
                id, 
                RANK() OVER (ORDER BY ts_rank_cd(search_vector, websearch_to_tsquery('english', :query_text)) DESC) as rank_lexical
            FROM papers
            WHERE search_vector @@ websearch_to_tsquery('english', :query_text)
            ORDER BY ts_rank_cd(search_vector, websearch_to_tsquery('english', :query_text)) DESC
            LIMIT :limit
        )
        SELECT 
            p.id, p.title, p.abstract, p.authors, p.pdf_url, p.source_url, p.published_at,
            COALESCE(1.0 / (:rrf_k + ss.rank_semantic), 0.0) + 
            COALESCE(1.0 / (:rrf_k + ls.rank_lexical), 0.0) as rrf_score
        FROM papers p
        FULL OUTER JOIN semantic_search ss ON p.id = ss.id
        FULL OUTER JOIN lexical_search ls ON p.id = ls.id
        WHERE ss.id IS NOT NULL OR ls.id IS NOT NULL
        ORDER BY rrf_score DESC
        LIMIT :limit
    """)
    
    # Dynamically bind parameter string representations mapping avoiding injection
    vector_str = f"[{','.join(map(str, query_embedding))}]"
    
    result = await session.execute(
        stmt, 
        {
            "embedding_val": vector_str,
            "query_text": query_text,
            "rrf_k": rrf_k,
            "limit": limit
        }
    )
    
    # Returning parsed memory bounds securely yielding Dictionary blocks natively!
    records = result.mappings().fetchall()
    return [dict(record) for record in records]
