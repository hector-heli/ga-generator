import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def sample_guide():
    return json.loads((ROOT / "data" / "sample_rae23.json").read_text(encoding="utf-8"))


@pytest.fixture
def empty_guide_data():
    from services.defaults import empty_guide

    return empty_guide()


@pytest.fixture
def client(tmp_path, monkeypatch):
    import app as app_module
    import config as config_module

    output_dir = tmp_path / "output"
    draft_dir = tmp_path / "drafts"
    output_dir.mkdir()
    draft_dir.mkdir()
    monkeypatch.setattr(app_module, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(app_module, "DRAFT_DIR", draft_dir)
    monkeypatch.setattr(config_module, "CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr(config_module, "GUIDES_DB", tmp_path / "guides.sqlite3")
    monkeypatch.setattr(config_module, "CATALOG_DB", tmp_path / "catalog.sqlite3")
    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as test_client:
        yield test_client
