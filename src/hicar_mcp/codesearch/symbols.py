"""A lightweight Fortran symbol index (modules, subroutines, functions, types).

Live mode only -- needs the source tree. Provides symbol lookup, body
extraction, and a path-safe file reader.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

_DEF = re.compile(
    r"^\s*(?:(?:pure|elemental|recursive|module|impure)\s+)*"
    r"(module(?!\s+procedure)|submodule|subroutine|function|interface|type)\b"
    r"(?:\s*\([^)]*\))?\s*(?:::\s*)?([A-Za-z]\w*)?",
    re.IGNORECASE,
)
_SRC_GLOBS = ("*.F90", "*.f90")
_IGNORE = {".git", "build", "build_debug", "build_snowpack_cpp", "external", "_deps", "__pycache__"}


@dataclass
class Symbol:
    kind: str
    name: str
    path: str   # relative to repo root
    line: int

    def to_dict(self) -> dict:
        return {"kind": self.kind, "name": self.name, "path": self.path, "line": self.line}


def _iter_source(repo_root: Path):
    src = repo_root / "src"
    base = src if src.exists() else repo_root
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in _IGNORE]
        for fn in filenames:
            if fn.endswith((".F90", ".f90")):
                yield Path(dirpath) / fn


def build_symbol_index(repo_root: Path) -> list[Symbol]:
    syms: list[Symbol] = []
    for fp in _iter_source(repo_root):
        rel = os.path.relpath(fp, repo_root)
        try:
            with open(fp, encoding="utf-8", errors="replace") as fh:
                for i, line in enumerate(fh, 1):
                    if "=" in line.split("!")[0]:
                        # skip "type = ..." style assignments
                        if re.match(r"\s*type\b", line, re.I) and "::" not in line:
                            continue
                    m = _DEF.match(line)
                    if not m or not m.group(2):
                        continue
                    kind = m.group(1).lower()
                    if kind == "type" and "::" not in line and "(" in line:
                        continue
                    syms.append(Symbol(kind=kind, name=m.group(2), path=rel, line=i))
        except OSError:
            continue
    return syms


def find_symbol(index: list[Symbol], name: str, kind: str | None = None) -> list[Symbol]:
    low = name.lower()
    out = [s for s in index if s.name.lower() == low and (kind is None or s.kind == kind.lower())]
    if not out:  # fall back to substring
        out = [s for s in index if low in s.name.lower() and (kind is None or s.kind == kind.lower())]
    return out


def safe_path(repo_root: Path, relpath: str) -> Path | None:
    """Resolve ``relpath`` under ``repo_root``, rejecting escapes."""
    try:
        target = (repo_root / relpath).resolve()
        root = repo_root.resolve()
        target.relative_to(root)
        return target
    except (ValueError, OSError):
        return None


def read_file(repo_root: Path, relpath: str, start: int | None = None, end: int | None = None) -> dict:
    target = safe_path(repo_root, relpath)
    if target is None or not target.exists() or not target.is_file():
        return {"error": f"path not found or outside repo: {relpath}"}
    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    s = max(1, start or 1)
    e = min(len(lines), end or len(lines))
    body = "\n".join(f"{i:6d}  {lines[i - 1]}" for i in range(s, e + 1))
    return {"path": relpath, "start": s, "end": e, "total_lines": len(lines), "text": body}


def read_symbol(repo_root: Path, sym: Symbol, max_lines: int = 400) -> dict:
    target = safe_path(repo_root, sym.path)
    if target is None:
        return {"error": "path outside repo"}
    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    start = sym.line
    end = len(lines)
    if sym.kind in ("subroutine", "function", "module", "submodule", "type", "interface"):
        endpat = re.compile(rf"^\s*end\s+{sym.kind}\b", re.IGNORECASE)
        for i in range(start, len(lines)):
            if endpat.match(lines[i]):
                end = i + 1
                break
    end = min(end, start + max_lines)
    return read_file(repo_root, sym.path, start, end)
