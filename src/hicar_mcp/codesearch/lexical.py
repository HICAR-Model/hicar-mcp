"""Lexical search: ripgrep when available, pure-Python fallback otherwise.

ripgrep is not a hard dependency (it is frequently absent); the fallback walks
the tree with ``re`` and returns the identical hit shape.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

DEFAULT_GLOBS = ("*.F90", "*.f90", "*.md")
_IGNORE_DIRS = {".git", "build", "build_debug", "build_snowpack_cpp", "external", "_deps",
                "__pycache__", "node_modules"}


@dataclass
class Hit:
    path: str
    line: int
    text: str

    def to_dict(self) -> dict:
        return {"path": self.path, "line": self.line, "text": self.text}


def have_ripgrep() -> bool:
    return shutil.which("rg") is not None


def _ignored(path: Path) -> bool:
    return any(part in _IGNORE_DIRS for part in path.parts)


def _rg(root: Path, pattern: str, regex: bool, globs, max_results: int) -> list[Hit]:
    cmd = ["rg", "--json", "-n", "--no-heading"]
    if not regex:
        cmd.append("-F")
    for g in globs:
        cmd += ["-g", g]
    for d in _IGNORE_DIRS:
        cmd += ["-g", f"!{d}/"]
    cmd += ["--", pattern, str(root)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return _python_search(root, pattern, regex, globs, max_results)
    hits: list[Hit] = []
    for line in proc.stdout.splitlines():
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get("type") != "match":
            continue
        d = obj["data"]
        hits.append(
            Hit(
                path=os.path.relpath(d["path"]["text"], root),
                line=d["line_number"],
                text=d["lines"]["text"].rstrip("\n"),
            )
        )
        if len(hits) >= max_results:
            break
    return hits


def _python_search(root: Path, pattern: str, regex: bool, globs, max_results: int) -> list[Hit]:
    if regex:
        rx = re.compile(pattern)
        match = rx.search
    else:
        low = pattern.lower()
        match = lambda s: low in s.lower()  # noqa: E731
    hits: list[Hit] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS]
        for fn in filenames:
            if not any(_match_glob(fn, g) for g in globs):
                continue
            fp = Path(dirpath) / fn
            try:
                with open(fp, encoding="utf-8", errors="replace") as fh:
                    for i, line in enumerate(fh, 1):
                        if match(line):
                            hits.append(Hit(os.path.relpath(fp, root), i, line.rstrip("\n")))
                            if len(hits) >= max_results:
                                return hits
            except OSError:
                continue
    return hits


def _match_glob(name: str, glob: str) -> bool:
    import fnmatch
    return fnmatch.fnmatch(name, glob)


def code_search(
    roots: list[Path],
    query: str,
    regex: bool = False,
    globs: tuple[str, ...] | None = None,
    max_results: int = 200,
) -> list[Hit]:
    globs = globs or DEFAULT_GLOBS
    use_rg = have_ripgrep()
    out: list[Hit] = []
    for root in roots:
        if not root or not root.exists():
            continue
        fn = _rg if use_rg else _python_search
        out.extend(fn(root, query, regex, globs, max_results - len(out)))
        if len(out) >= max_results:
            break
    return out[:max_results]
