from pathlib import Path

import pytest

from oai.config import ConfigError, find_repo_root, load_settings


def test_env_beats_dotenv_beats_toml(fake_repo, tmp_path):
    (fake_repo / ".env").write_text(
        f'OAI_DATA_DIR="{tmp_path / "from_dotenv"}"\nOAI_WORK_DIR="{tmp_path / "work_dotenv"}"\n'
    )
    cfg = fake_repo / "config" / "oai.toml"
    cfg.write_text(
        cfg.read_text()
        + f'\n[paths]\ndata_dir = "{tmp_path / "from_toml"}"\n'
        + f'work_dir = "{tmp_path / "work_toml"}"\ngeno_dir = "{tmp_path / "geno_toml"}"\n'
    )
    s = load_settings(env={"OAI_DATA_DIR": str(tmp_path / "from_env")}, repo_root=fake_repo)
    assert s.data_dir == (tmp_path / "from_env").resolve()
    assert s.work_dir == (tmp_path / "work_dotenv").resolve()
    assert s.geno_dir == (tmp_path / "geno_toml").resolve()


def test_missing_data_dir_raises_on_access(fake_repo):
    s = load_settings(env={}, repo_root=fake_repo)
    with pytest.raises(ConfigError, match="OAI_DATA_DIR is not set"):
        _ = s.data_dir


def test_empty_env_value_means_unset_and_blocks_dotenv(fake_repo, tmp_path):
    (fake_repo / ".env").write_text(f'OAI_GENO_DIR="{tmp_path / "geno"}"\n')
    s = load_settings(env={"OAI_GENO_DIR": ""}, repo_root=fake_repo)
    assert s.geno_dir is None


def test_work_dir_inside_repo_is_rejected(fake_repo):
    with pytest.raises(ConfigError, match="inside the repository"):
        load_settings(env={"OAI_WORK_DIR": str(fake_repo / "work")}, repo_root=fake_repo)


def test_relative_work_dir_resolves_against_repo_and_is_rejected(fake_repo):
    with pytest.raises(ConfigError, match="inside the repository"):
        load_settings(env={"OAI_WORK_DIR": "work"}, repo_root=fake_repo)


def test_results_dir_defaults_under_work_dir(fake_repo, tmp_path):
    s = load_settings(env={"OAI_WORK_DIR": str(tmp_path / "w")}, repo_root=fake_repo)
    assert s.results_dir == (tmp_path / "w" / "results").resolve()


def test_home_and_env_vars_are_expanded(fake_repo, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("OAI_TEST_BASE", str(tmp_path / "base"))
    s = load_settings(
        env={"OAI_DATA_DIR": "~/oai-data", "OAI_WORK_DIR": "$OAI_TEST_BASE/work"},
        repo_root=fake_repo,
    )
    assert s.data_dir == (tmp_path / "home" / "oai-data").resolve()
    assert s.work_dir == (tmp_path / "base" / "work").resolve()


def test_oai_config_override(fake_repo, tmp_path):
    other = tmp_path / "other.toml"
    other.write_text(f'[paths]\ndata_dir = "{tmp_path / "x"}"\n')
    s = load_settings(env={"OAI_CONFIG": str(other)}, repo_root=fake_repo)
    assert s.config_path == other.resolve()
    assert s.data_dir == (tmp_path / "x").resolve()


def test_missing_oai_config_file_raises(fake_repo, tmp_path):
    with pytest.raises(ConfigError, match="does not exist"):
        load_settings(env={"OAI_CONFIG": str(tmp_path / "nope.toml")}, repo_root=fake_repo)


def test_analyses_dir_defaults_to_repo(fake_repo):
    s = load_settings(env={}, repo_root=fake_repo)
    assert s.analyses_dir == fake_repo.resolve() / "analyses"


def test_analyses_dir_without_repo_requires_env():
    s = load_settings(env={}, repo_root=None)
    with pytest.raises(ConfigError, match="OAI_ANALYSES_DIR"):
        _ = s.analyses_dir


def test_find_repo_root_locates_this_checkout():
    root = find_repo_root()
    assert root is not None
    assert (root / "config" / "oai.toml").is_file()
    assert Path(__file__).resolve().is_relative_to(root)
