"""
Configuration for the year_scrape corpus builder.

Reads from environment or .env file. Falls back to the backend's .env.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

_this_dir = Path(__file__).parent
_backend_dir = _this_dir.parent / "backend"

if (_this_dir / ".env").exists():
    load_dotenv(_this_dir / ".env")
elif (_backend_dir / ".env").exists():
    load_dotenv(_backend_dir / ".env")

# Database — same Postgres as the main backend
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5433/arxiv_filter")
DATABASE_URL_SYNC = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

# Modal GPU for SPECTER2
MODAL_GPU_ENABLED = os.getenv("MODAL_GPU_ENABLED", "False").lower() == "true"
MODAL_TOKEN_ID = os.getenv("MODAL_TOKEN_ID")
MODAL_TOKEN_SECRET = os.getenv("MODAL_TOKEN_SECRET")

# ArXiv scraping
ARXIV_CATEGORY = os.getenv("ARXIV_CATEGORY", "cs.AI")
ARXIV_DELAY_SECONDS = float(os.getenv("ARXIV_DELAY_SECONDS", "5"))
ARXIV_PAGE_SIZE = int(os.getenv("ARXIV_PAGE_SIZE", "200"))

# Local file storage
DATA_DIR = _this_dir / "data"
PAPERS_JSONL = DATA_DIR / "papers.jsonl"
EMBEDDINGS_NPY = DATA_DIR / "embeddings.npy"
INDEX_JSON = DATA_DIR / "index.json"