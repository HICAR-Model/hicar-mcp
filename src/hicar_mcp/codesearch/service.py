"""Runtime semantic-search service: load/build the index, query, degrade.

Bundled mode loads the shipped index (``data/index``). Live mode builds and
caches an index under ``cache_dir`` and rebuilds it when the corpus changes.
If no embedder is available (``semantic`` extra missing / offline first run),
``search`` reports ``available=False`` and the server falls back to lexical.
"""

from __future__ import annotations

from pathlib import Path

from ..config import Config
from ..embed.base import make_embedder
from .semantic import SemanticIndex, chunk_repo, corpus_hash, index_is_fresh


class SemanticService:
    def __init__(self, config: Config):
        self.config = config
        self._index: SemanticIndex | None = None
        self._embedder = None
        self._embedder_tried = False
        self._note = ""

    def _get_embedder(self):
        if not self._embedder_tried:
            self._embedder_tried = True
            self._embedder = make_embedder(self.config.embedder_override)
            if self._embedder is None:
                self._note = (
                    "Semantic search unavailable: install the embedding model with "
                    "`pip install hicar-mcp[semantic]` (downloads once, then offline)."
                )
        return self._embedder

    def _bundled_index_dir(self) -> Path:
        return self.config.data_dir / "index"

    def _live_index_dir(self) -> Path:
        return self.config.cache_dir / "index"

    def _ensure_index(self, embedder) -> SemanticIndex | None:
        if self._index is not None:
            return self._index
        if self.config.mode == "bundled":
            d = self._bundled_index_dir()
            if (d / "embeddings.npy").exists():
                self._index = SemanticIndex.load(d)
                if self._index.meta.embedder != embedder.name:
                    self._note = (
                        f"Bundled index was built with '{self._index.meta.embedder}' but the "
                        f"active embedder is '{embedder.name}'; results may be poor."
                    )
            return self._index
        # live mode: build/cache
        repo = self.config.repo_root
        d = self._live_index_dir()
        if (d / "index_meta.json").exists():
            idx = SemanticIndex.load(d)
            if index_is_fresh(idx.meta, repo, embedder.name):
                self._index = idx
                return idx
        # (re)build
        chunks = chunk_repo(repo)
        idx = SemanticIndex.build(chunks, embedder, corpus_hash_=corpus_hash(repo))
        idx.save(d)
        self._index = idx
        return idx

    def available(self) -> bool:
        emb = self._get_embedder()
        if emb is None:
            return False
        if self.config.mode == "bundled":
            return (self._bundled_index_dir() / "embeddings.npy").exists()
        return self.config.repo_root is not None

    def search(self, query: str, k: int = 10, kind: str = "all") -> dict:
        emb = self._get_embedder()
        if emb is None:
            return {"available": False, "results": [], "note": self._note}
        try:
            idx = self._ensure_index(emb)
        except Exception as e:  # noqa: BLE001 - building can fail offline; degrade
            return {"available": False, "results": [], "note": f"index unavailable: {e}"}
        if idx is None or idx.embeddings.size == 0:
            return {"available": False, "results": [],
                    "note": self._note or "no semantic index found"}
        results = idx.search(query, emb, k=k, kind=kind)
        return {
            "available": True,
            "backend": emb.name,
            "index": {"chunks": idx.meta.count, "embedder": idx.meta.embedder},
            "results": results,
            "note": self._note,
        }
