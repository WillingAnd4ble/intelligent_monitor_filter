"""LLM response cache. Hash-keyed JSON files plus a committed manifest.

Cache key: sha256(paper_id || node || prompt_version || node_input || llm_model)
The cache directory itself is gitignored; the manifest lists what was cached.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from benchmark.lib import paths


def compute_key(paper_id: str, node: str, prompt_version: str,
                node_input: str, llm_model: str) -> str:
    """Stable sha256 hex key. Order matters; never reorder these fields."""
    h = hashlib.sha256()
    for part in (paper_id, node, prompt_version, node_input, llm_model):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")  # separator prevents accidental collisions
    return h.hexdigest()


def get(node: str, key: str) -> Optional[Dict[str, Any]]:
    p = paths.cache_path(node, key)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def put(node: str, key: str, payload: Dict[str, Any],
        paper_id: str, config_signature: str) -> None:
    p = paths.cache_path(node, key)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _append_manifest(key, paper_id, node, config_signature)


def _append_manifest(key: str, paper_id: str, node: str, config_signature: str) -> None:
    mp = paths.cache_manifest_path()
    entries = []
    if mp.exists():
        entries = json.loads(mp.read_text(encoding="utf-8"))
    entries.append({
        "hash": key,
        "paper_id": paper_id,
        "node": node,
        "config_signature": config_signature,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(entries, indent=2), encoding="utf-8")
