"""Settings resolution: process env -> .env -> config/oai.toml [paths] -> error.

An environment variable that is present but empty means "unset" and does not fall
through to .env, which lets tests and scripts switch a setting off explicitly.
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from oai.errors import OAIError

PATH_KEYS = ("OAI_DATA_DIR", "OAI_WORK_DIR", "OAI_RESULTS_DIR", "OAI_GENO_DIR", "OAI_ANALYSES_DIR")
MUST_BE_OUTSIDE_REPO = ("OAI_WORK_DIR", "OAI_RESULTS_DIR")
_AUTO: Any = object()


class ConfigError(OAIError):
    """A required setting is missing or unsafe."""


def find_repo_root(start: Path | None = None) -> Path | None:
    """Return the checkout root (has pyproject.toml and config/oai.toml), or None."""
    here = (start or Path(__file__)).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "config" / "oai.toml"
        ).is_file():
            return candidate
    return None


@dataclass(frozen=True)
class Settings:
    repo_root: Path | None
    config_path: Path | None
    project: Mapping[str, Any]
    paths: Mapping[str, Path] = field(default_factory=dict)

    def _require(self, key: str) -> Path:
        try:
            return self.paths[key]
        except KeyError:
            raise ConfigError(
                f"{key} is not set. Set it in the environment, in .env (see .env.example), "
                "or under [paths] in config/oai.toml."
            ) from None

    @property
    def data_dir(self) -> Path:
        return self._require("OAI_DATA_DIR")

    @property
    def work_dir(self) -> Path:
        return self._require("OAI_WORK_DIR")

    @property
    def results_dir(self) -> Path:
        return self.paths.get("OAI_RESULTS_DIR") or self.work_dir / "results"

    @property
    def geno_dir(self) -> Path | None:
        return self.paths.get("OAI_GENO_DIR")

    @property
    def analyses_dir(self) -> Path:
        if "OAI_ANALYSES_DIR" in self.paths:
            return self.paths["OAI_ANALYSES_DIR"]
        if self.repo_root is not None:
            return self.repo_root / "analyses"
        raise ConfigError("OAI_ANALYSES_DIR is not set and no repository checkout was found.")


def _lookup(
    key: str, sources: tuple[Mapping[str, str | None], ...], toml_paths: Mapping
) -> str | None:
    for source in sources:
        if key in source:
            return source[key] or None
    return toml_paths.get(key.removeprefix("OAI_").lower()) or None


def _normalize(raw: str, *, base: Path | None) -> Path:
    path = Path(os.path.expandvars(raw)).expanduser()
    if not path.is_absolute():
        path = (base or Path.cwd()) / path
    return path.resolve()


def _config_path(sources: tuple[Mapping[str, str | None], ...], root: Path | None) -> Path | None:
    for source in sources:
        if "OAI_CONFIG" in source:
            raw = source["OAI_CONFIG"]
            if raw:
                path = Path(raw).expanduser()
                if not path.is_file():
                    raise ConfigError(f"OAI_CONFIG={raw} does not exist")
                return path.resolve()
            break
    if root is not None and (root / "config" / "oai.toml").is_file():
        return root / "config" / "oai.toml"
    return None


def load_settings(
    *, env: Mapping[str, str] | None = None, repo_root: Path | None = _AUTO
) -> Settings:
    env = dict(os.environ if env is None else env)
    root = find_repo_root() if repo_root is _AUTO else repo_root
    root = root.resolve() if root is not None else None
    dotenv: dict[str, str | None] = {}
    if root is not None and (root / ".env").is_file():
        dotenv = dict(dotenv_values(root / ".env"))
    sources = (env, dotenv)
    config_path = _config_path(sources, root)
    project = tomllib.loads(config_path.read_text()) if config_path else {}
    toml_paths = project.get("paths", {})
    paths: dict[str, Path] = {}
    for key in PATH_KEYS:
        raw = _lookup(key, sources, toml_paths)
        if raw:
            paths[key] = _normalize(raw, base=root)
    if root is not None:
        for key in MUST_BE_OUTSIDE_REPO:
            if key in paths and paths[key].is_relative_to(root):
                raise ConfigError(
                    f"{key}={paths[key]} is inside the repository ({root}). "
                    "Derived data must live outside the repo."
                )
    return Settings(repo_root=root, config_path=config_path, project=project, paths=paths)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings (cached; tests clear the cache)."""
    return load_settings()
