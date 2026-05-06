"""Benchmark harness library — pure Python, no Streamlit imports.

On first import, populate os.environ from backend/.env and testing/.env.benchmark
so backend modules (which instantiate pydantic Settings at import time) work.
"""

import os as _os
from pathlib import Path as _Path


def _load_env_file(path: _Path) -> None:
    """Populate os.environ from a .env file. First-loaded value wins."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            _os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# This file lives at testing/benchmark/lib/__init__.py.
# parents[3] is the repo root.
_REPO_ROOT = _Path(__file__).resolve().parents[3]
_load_env_file(_REPO_ROOT / "backend" / ".env")
_load_env_file(_REPO_ROOT / "testing" / ".env.benchmark")
