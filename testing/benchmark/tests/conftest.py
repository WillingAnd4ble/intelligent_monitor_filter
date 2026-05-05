import pytest
import tempfile
from pathlib import Path

@pytest.fixture
def tmp_data_dir(monkeypatch):
    """Redirect data/ writes to a tempdir for tests."""
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("BENCHMARK_DATA_DIR", tmp)
        yield Path(tmp)
