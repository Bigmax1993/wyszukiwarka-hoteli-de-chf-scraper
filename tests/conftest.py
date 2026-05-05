import importlib.util
import logging
import sys
import types
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

SCRAPER_PATH = PROJECT_DIR / "scraper.py"
_source = SCRAPER_PATH.read_text(encoding="utf-8")
_cut_marker = '\nif __name__ == "__main__":\n'
if _cut_marker in _source:
    _source = _source.split(_cut_marker, 1)[0]
_module = types.ModuleType("scraper")
_module.__file__ = str(SCRAPER_PATH)
exec(compile(_source, str(SCRAPER_PATH), "exec"), _module.__dict__)
sys.modules["scraper"] = _module


@pytest.fixture(scope="session")
def scraper_module():
    return _module


@pytest.fixture
def logger():
    return logging.getLogger("test-scraper")


@pytest.fixture
def isolated_paths(tmp_path, monkeypatch, scraper_module):
    out_dir = tmp_path / "Wyniki"
    out_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(scraper_module, "OUTPUT_DIR", out_dir)
    monkeypatch.setattr(scraper_module, "OUTPUT_FILE", out_dir / "out.csv")
    monkeypatch.setattr(scraper_module, "CACHE_FILE", out_dir / "cache.json")
    monkeypatch.setattr(scraper_module, "LOG_FILE", out_dir / "scraper.log")
    return out_dir
