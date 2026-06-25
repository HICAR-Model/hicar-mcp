"""Semantic search over Fortran + markdown via a brute-force numpy index.

The corpus is chunked (Fortran by procedure, markdown by heading), embedded,
and stored as ``embeddings.npy`` + ``chunks.jsonl`` + ``index_meta.json``.
The index is built in CI and bundled; at query time the *same* embedder embeds
the query and we take the top-k cosine matches. Chunk text is stored, so
bundled mode returns snippets without shipping full source.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from ..embed.base import Embedder

_DEF = re.compile(r"^\s*(?:(?:pure|elemental|recursive|module|impure)\s+)*"
                  r"(subroutine|function|module|submodule)\b\s*(?:\([^)]*\))?\s*([A-Za-z]\w*)?", re.I)
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_MAX_CODE_LINES = 120
_IGNORE = {".git", "build", "build_debug", "build_snowpack_cpp", "external", "_deps", "__pycache__"}


@dataclass
class Chunk:
    id: int
    path: str
    start_line: int
    end_line: int
    kind: str          # "code" | "docs"
    title: str
    text: str


def _iter_files(repo_root: Path):
    for sub, globs, kind in (("src", (".F90", ".f90"), "code"), ("docs", (".md",), "docs")):
        base = repo_root / sub
        if not base.exists():
            continue
        for dp, dn, fns in os.walk(base):
            dn[:] = [d for d in dn if d not in _IGNORE]
            for fn in sorted(fns):
                if fn.endswith(globs):
                    yield Path(dp) / fn, kind


def _chunk_code(rel: str, lines: list[str]) -> list[tuple[int, int, str, str]]:
    """Return (start, end, title, text) by procedure, splitting long ones."""
    bounds = [i for i, ln in enumerate(lines) if _DEF.match(ln)]
    if not bounds or bounds[0] != 0:
        bounds = [0] + bounds
    segs: list[tuple[int, int]] = []
    for j, b in enumerate(bounds):
        e = bounds[j + 1] if j + 1 < len(bounds) else len(lines)
        segs.append((b, e))
    out = []
    for b, e in segs:
        m = _DEF.match(lines[b]) if b < len(lines) else None
        title = (m.group(2) if m and m.group(2) else rel)
        for s in range(b, e, _MAX_CODE_LINES):
            ss = s
            se = min(e, s + _MAX_CODE_LINES)
            out.append((ss + 1, se, title, "\n".join(lines[ss:se])))
    return out


def _chunk_docs(rel: str, lines: list[str]) -> list[tuple[int, int, str, str]]:
    out = []
    cur_start = 0
    cur_title = rel
    for i, ln in enumerate(lines):
        m = _HEADING.match(ln)
        if m and i > cur_start:
            out.append((cur_start + 1, i, cur_title, "\n".join(lines[cur_start:i])))
            cur_start = i
            cur_title = m.group(2).strip()
        elif m:
            cur_title = m.group(2).strip()
    out.append((cur_start + 1, len(lines), cur_title, "\n".join(lines[cur_start:])))
    return [c for c in out if c[3].strip()]


def chunk_repo(repo_root: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    cid = 0
    for fp, kind in _iter_files(repo_root):
        rel = os.path.relpath(fp, repo_root)
        try:
            lines = fp.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        pieces = _chunk_code(rel, lines) if kind == "code" else _chunk_docs(rel, lines)
        for start, end, title, text in pieces:
            if not text.strip():
                continue
            chunks.append(Chunk(cid, rel, start, end, kind, title, text))
            cid += 1
    return chunks


def corpus_hash(repo_root: Path) -> str:
    h = hashlib.sha256()
    items = []
    for fp, _ in _iter_files(repo_root):
        try:
            st = fp.stat()
            items.append((os.path.relpath(fp, repo_root), st.st_size, st.st_mtime_ns))
        except OSError:
            continue
    for rel, size, mtime in sorted(items):
        h.update(f"{rel}:{size}:{mtime}".encode())
    return h.hexdigest()


@dataclass
class IndexMeta:
    embedder: str
    dim: int
    count: int
    corpus_hash: str
    built_at: str | None = None


class SemanticIndex:
    def __init__(self, chunks: list[Chunk], embeddings: np.ndarray, meta: IndexMeta):
        self.chunks = chunks
        self.embeddings = embeddings
        self.meta = meta

    @classmethod
    def build(cls, chunks: list[Chunk], embedder: Embedder,
              corpus_hash_: str = "", built_at: str | None = None) -> "SemanticIndex":
        texts = [f"{c.path} :: {c.title}\n{c.text}" for c in chunks]
        embs = embedder.encode(texts, is_query=False) if texts else np.zeros((0, embedder.dim), np.float32)
        meta = IndexMeta(embedder.name, int(embs.shape[1]) if embs.size else embedder.dim,
                         len(chunks), corpus_hash_, built_at)
        return cls(chunks, embs.astype(np.float32), meta)

    def save(self, out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        np.save(out_dir / "embeddings.npy", self.embeddings)
        with open(out_dir / "chunks.jsonl", "w", encoding="utf-8") as fh:
            for c in self.chunks:
                fh.write(json.dumps(asdict(c)) + "\n")
        (out_dir / "index_meta.json").write_text(json.dumps(asdict(self.meta), indent=2))

    @classmethod
    def load(cls, in_dir: Path) -> "SemanticIndex":
        embs = np.load(in_dir / "embeddings.npy")
        chunks = []
        with open(in_dir / "chunks.jsonl", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    chunks.append(Chunk(**json.loads(line)))
        meta = IndexMeta(**json.loads((in_dir / "index_meta.json").read_text()))
        return cls(chunks, embs, meta)

    def search(self, query: str, embedder: Embedder, k: int = 10,
               kind: str | None = None) -> list[dict]:
        if self.embeddings.size == 0:
            return []
        qv = embedder.encode([query], is_query=True)[0]
        scores = self.embeddings @ qv
        order = np.argsort(-scores)
        out = []
        for idx in order:
            c = self.chunks[int(idx)]
            if kind and kind != "all" and c.kind != kind:
                continue
            snippet = c.text if len(c.text) <= 1200 else c.text[:1200] + "\n..."
            out.append({
                "path": c.path, "start_line": c.start_line, "end_line": c.end_line,
                "kind": c.kind, "title": c.title, "score": round(float(scores[idx]), 4),
                "text": snippet,
            })
            if len(out) >= k:
                break
        return out


def index_is_fresh(meta: IndexMeta, repo_root: Path, embedder_name: str) -> bool:
    return meta.embedder == embedder_name and meta.corpus_hash == corpus_hash(repo_root)
