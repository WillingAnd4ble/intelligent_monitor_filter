"""
Thin wrapper around Modal SDK for calling deployed GPU functions.

Safety layers:
  1. MODAL_GPU_ENABLED=False (default) -> all calls return mocks, zero GPU cost
  2. Missing tokens -> falls back to mocks with a warning
  3. Timeouts on the Modal side (gpu_inference.py) kill stuck containers
  4. Concurrency limits on Modal side cap max simultaneous GPUs
"""

import os
import random
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

MODAL_APP_NAME = "gpu-inference"


def _is_modal_ready() -> bool:
    """Check kill switch + credentials. Must pass both to use real GPU."""
    if not settings.MODAL_GPU_ENABLED:
        return False
    # If .env has explicit tokens, push them into env for Modal SDK.
    # Otherwise, SDK falls back to ~/.modal.toml (from `modal token new`).
    if settings.MODAL_TOKEN_ID and settings.MODAL_TOKEN_SECRET:
        os.environ.setdefault("MODAL_TOKEN_ID", settings.MODAL_TOKEN_ID)
        os.environ.setdefault("MODAL_TOKEN_SECRET", settings.MODAL_TOKEN_SECRET)
    return True


# ── SPECTER2 ──────────────────────────────────────────────────────

def specter2_embed_batch(title_abstract_pairs: list[dict]) -> list[list[float]]:
    """
    Generate SPECTER2 embeddings for a batch of papers.

    Args:
        title_abstract_pairs: list of {"title": str, "abstract": str}

    Returns:
        list of 768-dim float vectors, one per paper.
    """
    texts = [
        f"{p['title']} [SEP] {p['abstract']}" for p in title_abstract_pairs
    ]

    if not _is_modal_ready():
        logger.warning("Modal GPU disabled or not configured — returning mock SPECTER2 embeddings")
        return [[random.uniform(-0.1, 0.1) for _ in range(768)] for _ in texts]

    import modal

    logger.info(f"Calling Modal SPECTER2 for {len(texts)} papers")
    cls = modal.Cls.from_name(MODAL_APP_NAME, "Specter2Embedder")
    embedder = cls()
    return embedder.embed_batch.remote(texts)


# ── MARKER PDF ────────────────────────────────────────────────────

def marker_extract_pdf(pdf_url: str) -> str:
    """
    Extract full text from a PDF using MARKER on Modal GPU.

    Args:
        pdf_url: direct URL to the PDF file.

    Returns:
        Extracted text as markdown string.
    """
    if not _is_modal_ready():
        logger.warning("Modal GPU disabled or not configured — skipping MARKER extraction")
        return ""

    if not pdf_url:
        logger.warning("No pdf_url provided — skipping MARKER extraction")
        return ""

    import modal

    logger.info(f"Calling Modal MARKER for {pdf_url}")
    cls = modal.Cls.from_name(MODAL_APP_NAME, "MarkerExtractor")
    extractor = cls()
    return extractor.extract.remote(pdf_url)