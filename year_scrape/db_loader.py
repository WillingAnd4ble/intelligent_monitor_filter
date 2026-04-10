"""
Load the scraped + embedded corpus into the main backend's PostgreSQL database.

This writes papers (with real SPECTER2 embeddings) into the same `papers` table
that the backend uses, so the hybrid RRF search can query against the full year.

Usage:
    python db_loader.py                    # load all papers not yet in DB
    python db_loader.py --dry-run          # show what would be inserted
"""

import json
import logging
import numpy as np
from datetime import datetime, timezone

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def load_corpus():
    """Load papers + embeddings from local files."""
    papers = []
    with open(config.PAPERS_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            papers.append(json.loads(line))

    embeddings = np.load(config.EMBEDDINGS_NPY)
    with open(config.INDEX_JSON, "r") as f:
        index = json.load(f)

    # Build a dict: paper_id → embedding
    id_to_emb = {}
    for i, pid in enumerate(index):
        id_to_emb[pid] = embeddings[i].tolist()

    return papers, id_to_emb


def load_into_db(dry_run: bool = False):
    """
    Insert papers + embeddings into the backend's PostgreSQL `papers` table.

    Uses synchronous psycopg2 for simplicity (bulk insert doesn't need async).
    Also populates the search_vector TSVECTOR column for BM25.
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    papers, id_to_emb = load_corpus()
    logger.info(f"Loaded {len(papers)} papers, {len(id_to_emb)} embeddings")

    engine = create_engine(config.DATABASE_URL_SYNC, echo=False)

    with Session(engine) as session:
        # Get existing paper IDs
        result = session.execute(text("SELECT id FROM papers"))
        existing_ids = {row[0] for row in result.fetchall()}
        logger.info(f"Already in DB: {len(existing_ids)} papers")

        to_insert = [p for p in papers if p["paper_id"] not in existing_ids]
        logger.info(f"New papers to insert: {len(to_insert)}")

        if dry_run:
            for p in to_insert[:10]:
                has_emb = p["paper_id"] in id_to_emb
                logger.info(f"  [DRY RUN] Would insert {p['paper_id']}: "
                            f"{p['title'][:60]}... (embedding: {has_emb})")
            if len(to_insert) > 10:
                logger.info(f"  ... and {len(to_insert) - 10} more")
            return

        inserted = 0
        for p in to_insert:
            embedding = id_to_emb.get(p["paper_id"])
            emb_str = f"[{','.join(map(str, embedding))}]" if embedding else None

            session.execute(
                text("""
                    INSERT INTO papers (id, title, authors, abstract, pdf_url, source_url, published_at, embedding)
                    VALUES (:id, :title, :authors, :abstract, :pdf_url, :source_url, :published_at,
                            CASE WHEN :embedding IS NOT NULL THEN CAST(:embedding AS vector) ELSE NULL END)
                    ON CONFLICT (id) DO NOTHING
                """),
                {
                    "id": p["paper_id"],
                    "title": p["title"],
                    "authors": json.dumps(p["authors"]),
                    "abstract": p["abstract"],
                    "pdf_url": p.get("pdf_url"),
                    "source_url": p.get("source_url"),
                    "published_at": p["published_at"],
                    "embedding": emb_str,
                },
            )
            inserted += 1

            if inserted % 500 == 0:
                session.commit()
                logger.info(f"  Committed {inserted} papers ...")

        session.commit()
        logger.info(f"Inserted {inserted} papers")

        # Populate TSVECTOR for all papers missing it
        logger.info("Populating TSVECTOR search_vector for BM25 ...")
        session.execute(text("""
            UPDATE papers
            SET search_vector = to_tsvector('english', title || ' ' || abstract)
            WHERE search_vector IS NULL
        """))
        session.commit()
        logger.info("Done. TSVECTOR populated.")

    engine.dispose()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    load_into_db(dry_run=args.dry_run)