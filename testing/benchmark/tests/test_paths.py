from pathlib import Path
import os
from benchmark.lib import paths

def test_data_root_uses_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("BENCHMARK_DATA_DIR", str(tmp_path))
    assert paths.data_root() == tmp_path

def test_goal_path_format(monkeypatch, tmp_path):
    monkeypatch.setenv("BENCHMARK_DATA_DIR", str(tmp_path))
    p = paths.goal_path("security_v1")
    assert p == tmp_path / "goals" / "security_v1.json"

def test_candidates_path_format(monkeypatch, tmp_path):
    monkeypatch.setenv("BENCHMARK_DATA_DIR", str(tmp_path))
    p = paths.candidates_path("security_v1", "rrf")
    assert p == tmp_path / "candidates" / "security_v1__rrf.json"

def test_labels_path_format(monkeypatch, tmp_path):
    monkeypatch.setenv("BENCHMARK_DATA_DIR", str(tmp_path))
    p = paths.labels_path("security_v1")
    assert p == tmp_path / "labels" / "security_v1.json"

def test_result_path_format(monkeypatch, tmp_path):
    monkeypatch.setenv("BENCHMARK_DATA_DIR", str(tmp_path))
    p = paths.result_path("security_v1__abc12345__2026-04-13T16:05Z")
    assert p == tmp_path / "results" / "security_v1__abc12345__2026-04-13T16:05Z.json"
