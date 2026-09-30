"""Shared pytest fixtures.

Every test runs with OAI_* settings pointed at throwaway locations so a developer's
real .env never leaks into the suite. Tests marked `realdata` keep the developer's
OAI_DATA_DIR and are skipped when it is not configured.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from oai import catalog as oai_catalog
from oai import config as oai_config

FIXTURES = Path(__file__).parent / "fixtures"
OAI_FIXTURE_DATA = FIXTURES / "oai"
REPO_ROOT = Path(__file__).resolve().parents[1]


def _clear_caches() -> None:
    oai_config.get_settings.cache_clear()
    oai_catalog.catalog_for.cache_clear()


@pytest.fixture(autouse=True)
def isolated_settings(request, tmp_path, monkeypatch):
    if request.node.get_closest_marker("realdata"):
        try:
            data_dir = oai_config.load_settings().data_dir
        except oai_config.ConfigError:
            pytest.skip("OAI_DATA_DIR is not configured (env or .env)")
    else:
        data_dir = OAI_FIXTURE_DATA
    monkeypatch.setenv("OAI_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OAI_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("OAI_RESULTS_DIR", str(tmp_path / "results"))
    for key in ("OAI_GENO_DIR", "OAI_ANALYSES_DIR", "OAI_CONFIG", "OAI_FRAME_DIR"):
        monkeypatch.setenv(key, "")
    _clear_caches()
    yield
    _clear_caches()


@pytest.fixture
def fake_repo(tmp_path) -> Path:
    """A minimal checkout: pyproject.toml plus a copy of the real config/oai.toml."""
    root = tmp_path / "repo"
    (root / "config").mkdir(parents=True)
    (root / "pyproject.toml").write_text('[project]\nname = "fake"\n')
    (root / "config" / "oai.toml").write_text((REPO_ROOT / "config" / "oai.toml").read_text())
    return root
