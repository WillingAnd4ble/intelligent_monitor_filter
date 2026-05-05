import json
from benchmark.lib import cache


def test_compute_key_is_deterministic():
    k1 = cache.compute_key("paper1", "evaluator", "v1", "input-text", "gpt-4o-mini")
    k2 = cache.compute_key("paper1", "evaluator", "v1", "input-text", "gpt-4o-mini")
    assert k1 == k2
    assert len(k1) == 64  # full sha256 hex


def test_compute_key_changes_on_any_field():
    base = cache.compute_key("p", "evaluator", "v1", "x", "m")
    assert cache.compute_key("p2", "evaluator", "v1", "x", "m") != base
    assert cache.compute_key("p", "critique", "v1", "x", "m") != base
    assert cache.compute_key("p", "evaluator", "v2", "x", "m") != base
    assert cache.compute_key("p", "evaluator", "v1", "y", "m") != base
    assert cache.compute_key("p", "evaluator", "v1", "x", "m2") != base


def test_get_returns_none_on_miss(monkeypatch, tmp_path):
    monkeypatch.setenv("BENCHMARK_DATA_DIR", str(tmp_path))
    assert cache.get("evaluator", "deadbeef" * 8) is None


def test_put_then_get_roundtrips(monkeypatch, tmp_path):
    monkeypatch.setenv("BENCHMARK_DATA_DIR", str(tmp_path))
    payload = {"decision": "accept", "score": 7.5, "tokens_in": 100, "tokens_out": 20, "latency_ms": 420}
    key = "ab" * 32
    cache.put("evaluator", key, payload, paper_id="p1", config_signature="cfg-sig")
    got = cache.get("evaluator", key)
    assert got == payload


def test_put_appends_manifest_entry(monkeypatch, tmp_path):
    monkeypatch.setenv("BENCHMARK_DATA_DIR", str(tmp_path))
    payload = {"decision": "accept"}
    cache.put("evaluator", "ab" * 32, payload, paper_id="p1", config_signature="cfg-sig")
    cache.put("critique", "cd" * 32, payload, paper_id="p2", config_signature="cfg-sig")
    manifest = json.loads((tmp_path / "cache_manifest.json").read_text())
    assert len(manifest) == 2
    nodes = {e["node"] for e in manifest}
    assert nodes == {"evaluator", "critique"}
