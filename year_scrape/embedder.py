"""
Batch SPECTER2 embedding generator for the scraped corpus.

Reads papers.jsonl, generates 768-dim embeddings via Modal GPU,
saves them as a numpy array + index mapping.

Usage:
    python embedder.py                      # embed all un-embedded papers
    python embedder.py --batch-size 64      # control GPU batch size
"""

import json
import logging
import numpy as np
from pathlib import Path

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def load_papers(path: Path = None) -> list[dict]:
    """Load papers from JSONL file."""
    path = path or config.PAPERS_JSONL
    papers = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            papers.append(json.loads(line))
    return papers


def embed_via_modal(texts: list[str]) -> list[list[float]]:
    """Call Modal GPU SPECTER2 embedder."""
    import os
    if config.MODAL_TOKEN_ID and config.MODAL_TOKEN_SECRET:
        os.environ.setdefault("MODAL_TOKEN_ID", config.MODAL_TOKEN_ID)
        os.environ.setdefault("MODAL_TOKEN_SECRET", config.MODAL_TOKEN_SECRET)

    import modal
    cls = modal.Cls.from_name("gpu-inference", "Specter2Embedder")
    embedder = cls()
    return embedder.embed_batch.remote(texts)


def embed_corpus(batch_size: int = 64):
    """
    Generate SPECTER2 embeddings for all papers in papers.jsonl.

    Saves:
      - data/embeddings.npy:  (N, 768) float32 array
      - data/index.json:      maps row index → paper_id
    """
    papers = load_papers()
    logger.info(f"Loaded {len(papers)} papers from {config.PAPERS_JSONL}")

    # Load existing embeddings to allow resuming
    existing_ids = set()
    existing_embeddings = []
    existing_index = []

    if config.EMBEDDINGS_NPY.exists() and config.INDEX_JSON.exists():
        existing_embeddings_arr = np.load(config.EMBEDDINGS_NPY)
        existing_embeddings = existing_embeddings_arr.tolist()
        with open(config.INDEX_JSON, "r") as f:
            existing_index = json.load(f)
        existing_ids = set(existing_index)
        logger.info(f"Resuming: {len(existing_ids)} papers already embedded")

    # Filter to un-embedded papers
    to_embed = [p for p in papers if p["paper_id"] not in existing_ids]
    if not to_embed:
        logger.info("All papers already embedded. Nothing to do.")
        return

    logger.info(f"Embedding {len(to_embed)} new papers in batches of {batch_size}")

    all_new_embeddings = []
    all_new_ids = []

    for i in range(0, len(to_embed), batch_size):
        batch = to_embed[i : i + batch_size]
        texts = [f"{p['title']} [SEP] {p['abstract']}" for p in batch]

        logger.info(f"  Batch {i // batch_size + 1}: {len(batch)} papers ...")

        if config.MODAL_GPU_ENABLED:
            embeddings = embed_via_modal(texts)
        else:
            logger.warning("Modal disabled — generating random mock embeddings")
            import random
            embeddings = [[random.uniform(-0.1, 0.1) for _ in range(768)] for _ in texts]

        all_new_embeddings.extend(embeddings)
        all_new_ids.extend([p["paper_id"] for p in batch])

    # Merge with existing
    full_index = existing_index + all_new_ids
    if existing_embeddings:
        full_arr = np.array(existing_embeddings + all_new_embeddings, dtype=np.float32)
    else:
        full_arr = np.array(all_new_embeddings, dtype=np.float32)

    # Save
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    np.save(config.EMBEDDINGS_NPY, full_arr)
    with open(config.INDEX_JSON, "w") as f:
        json.dump(full_index, f)

    logger.info(
        f"Done. Saved {full_arr.shape[0]} embeddings "
        f"({full_arr.shape[1]}-dim) to {config.EMBEDDINGS_NPY}"
    )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()
    embed_corpus(batch_size=args.batch_size)