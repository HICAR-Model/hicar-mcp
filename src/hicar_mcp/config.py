"""Path & mode discovery.

The server runs in one of two modes:

* **bundled** (default) — load pre-extracted artifacts shipped inside the
  package (``hicar_mcp/data``). Works with zero configuration and no HICAR
  checkout.
* **live** — if ``HICAR_REPO`` (or ``HICAR_MCP_REPO``) points at a HICAR
  checkout, parse the source directly so working-tree changes are reflected.
  Enables source-aware tools (``code_search``, ``read_source``).
"""

from __future__ import annotations

import glob
import os
from dataclasses import dataclass
from pathlib import Path

# Files that uniquely identify a HICAR checkout root.
_REPO_MARKERS = ("src/utilities/namelist_utilities.F90", "CMakeLists.txt")

# Source-of-truth files within a HICAR checkout (relative to repo root).
NAMELIST_UTIL = "src/utilities/namelist_utilities.F90"
CONSTANTS = "src/constants/icar_constants.F90"
OUTPUT_META = "src/io/default_output_metadata.F90"
DRIVER = "src/main/driver.F90"
DOCS_DIR = "docs"
MKDOCS = "mkdocs.yml"
EXAMPLES_DIR = "helpers/example_namelists"
TEST_INPUT_DIR = "tests/Test_Cases/input"
NAMELIST_DOC = "bin/namelist_doc.txt"


@dataclass
class Config:
    mode: str                       # "live" | "bundled"
    repo_root: Path | None          # HICAR checkout (live mode only)
    data_dir: Path                  # bundled artifacts dir (always present)
    binary: Path | None             # compiled HICAR, if found
    cache_dir: Path                 # writable scratch (never inside a repo)
    embedder_override: str | None   # HICAR_MCP_EMBEDDER

    # -- convenience resolvers (live mode) --
    def src_file(self, rel: str) -> Path | None:
        if self.repo_root is None:
            return None
        p = self.repo_root / rel
        return p if p.exists() else None

    @property
    def namelist_doc(self) -> Path | None:
        """Optional enrichment file; gitignored, so usually absent."""
        return self.src_file(NAMELIST_DOC)


def _looks_like_repo(p: Path) -> bool:
    return all((p / m).exists() for m in _REPO_MARKERS)


def _find_repo_root() -> Path | None:
    # 1. explicit env
    for var in ("HICAR_REPO", "HICAR_MCP_REPO"):
        v = os.environ.get(var)
        if v:
            p = Path(v).expanduser().resolve()
            if _looks_like_repo(p):
                return p
            # tolerate being pointed one level off
            for cand in (p.parent, *p.glob("HICAR")):
                if _looks_like_repo(cand):
                    return cand
            return None  # explicitly set but invalid -> stay bundled, surfaced by doctor
    # 2. walk up from CWD
    for base in (Path.cwd(), Path(__file__).resolve().parent):
        for cand in (base, *base.parents):
            if _looks_like_repo(cand):
                return cand
    return None


def _find_binary(repo_root: Path | None) -> Path | None:
    env = os.environ.get("HICAR_BINARY")
    if env:
        p = Path(env).expanduser()
        return p if p.exists() else None
    if repo_root is None:
        return None
    candidates = [repo_root / "bin" / "HICAR"]
    candidates += [Path(x) for x in glob.glob(str(repo_root / "build*" / "HICAR"))]
    for c in candidates:
        if c.exists() and os.access(c, os.X_OK):
            return c
    return None


def _cache_dir(repo_root: Path | None) -> Path:
    env = os.environ.get("HICAR_MCP_CACHE")
    if env:
        base = Path(env).expanduser()
    else:
        xdg = os.environ.get("XDG_CACHE_HOME")
        base = (Path(xdg) if xdg else Path.home() / ".cache") / "hicar-mcp"
    # Namespace by repo so multiple checkouts don't collide.
    tag = "bundled" if repo_root is None else str(abs(hash(str(repo_root))) % (1 << 32))
    d = base / tag
    d.mkdir(parents=True, exist_ok=True)
    return d


def bundled_data_dir() -> Path:
    return Path(__file__).resolve().parent / "data"


def discover() -> Config:
    repo_root = _find_repo_root()
    mode = "live" if repo_root is not None else "bundled"
    return Config(
        mode=mode,
        repo_root=repo_root,
        data_dir=bundled_data_dir(),
        binary=_find_binary(repo_root),
        cache_dir=_cache_dir(repo_root),
        embedder_override=os.environ.get("HICAR_MCP_EMBEDDER"),
    )
