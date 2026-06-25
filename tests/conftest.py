from __future__ import annotations

from pathlib import Path

import pytest

from hicar_mcp.config import Config
from hicar_mcp.extract.runner import extract_from_repo, write_artifacts
from hicar_mcp.artifacts.loader import load_bundled

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def fixtures_repo() -> Path:
    return FIXTURES / "repo"


@pytest.fixture(scope="session")
def nml_util_text(fixtures_repo) -> str:
    return (fixtures_repo / "src/utilities/namelist_utilities.F90").read_text()


@pytest.fixture(scope="session")
def constants_text(fixtures_repo) -> str:
    return (fixtures_repo / "src/constants/icar_constants.F90").read_text()


@pytest.fixture(scope="session")
def kn_live(fixtures_repo):
    return extract_from_repo(fixtures_repo)


@pytest.fixture()
def bundled_dir(tmp_path, kn_live) -> Path:
    out = tmp_path / "data"
    write_artifacts(kn_live, out, hicar_version_str=kn_live.version["hicar_version"],
                    built_at="2026-01-01")
    return out


@pytest.fixture()
def kn_bundled(bundled_dir):
    return load_bundled(bundled_dir)


@pytest.fixture()
def live_config(fixtures_repo, tmp_path) -> Config:
    return Config(
        mode="live", repo_root=fixtures_repo, data_dir=fixtures_repo,
        binary=None, cache_dir=tmp_path / "cache", embedder_override="fake",
    )


@pytest.fixture()
def bundled_config(bundled_dir, tmp_path) -> Config:
    (tmp_path / "cache").mkdir(exist_ok=True)
    return Config(
        mode="bundled", repo_root=None, data_dir=bundled_dir,
        binary=None, cache_dir=tmp_path / "cache", embedder_override="fake",
    )
