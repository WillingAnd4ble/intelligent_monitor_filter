"""Dataset partitions: named, frozen snapshots of paper-id sets.

A goal references a dataset_id. Retrievers filter on that paper_ids list so
all goals tied to the same dataset query the exact same paper population —
even months later, even if the prod papers table grows.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import List, Optional, Set

from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from benchmark.lib import paths
from benchmark.lib.schemas import DatasetFile


def _engine_url() -> str:
    url = os.environ.get("BENCHMARK_DB_URL") or ""
    if not url or "readonly_user:password" in url:
        url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("Neither BENCHMARK_DB_URL nor DATABASE_URL is set.")
    return url


async def _all_paper_ids() -> List[str]:
    engine = create_async_engine(_engine_url(), future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        rows = (await s.execute(sql_text(
            "SELECT id FROM papers WHERE embedding IS NOT NULL ORDER BY published_at DESC"
        ))).fetchall()
    return [r[0] for r in rows]


def list_datasets() -> List[str]:
    root = paths.data_root() / "datasets"
    if not root.exists():
        return []
    return sorted(f.stem for f in root.glob("*.json"))


def load(dataset_id: str) -> DatasetFile:
    p = paths.dataset_path(dataset_id)
    return DatasetFile.model_validate_json(p.read_text(encoding="utf-8"))


def paper_ids_for(dataset_id: Optional[str]) -> Optional[Set[str]]:
    """Return the set of paper IDs for the dataset, or None for "no restriction"."""
    if not dataset_id:
        return None
    return set(load(dataset_id).paper_ids)


def create_from_current_papers(dataset_id: str, description: str) -> DatasetFile:
    """Snapshot all papers in the prod DB right now into a frozen dataset.

    Refuses to overwrite an existing dataset of the same name.
    """
    p = paths.dataset_path(dataset_id)
    if p.exists():
        raise FileExistsError(
            f"{p} already exists — datasets are frozen. Use a new dataset_id."
        )

    paper_ids = asyncio.run(_all_paper_ids())
    df = DatasetFile(
        dataset_id=dataset_id,
        description=description,
        created_at=datetime.now(timezone.utc),
        paper_ids=paper_ids,
        paper_count=len(paper_ids),
        source_query="all papers in prod DB with embedding IS NOT NULL",
    )
    paths.ensure_subdirs()
    p.write_text(df.model_dump_json(indent=2), encoding="utf-8")
    return df
