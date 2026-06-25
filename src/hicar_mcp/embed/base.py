"""Embedder protocol + factory.

Selection precedence (see ``make_embedder``):
  explicit spec  ->  API (key + extra)  ->  local (offline, default)  ->  None.

Returning ``None`` is normal (e.g. the ``semantic`` extra isn't installed); the
caller falls back to lexical search.
"""

from __future__ import annotations

import hashlib
import os
from typing import Protocol, runtime_checkable

import numpy as np

DEFAULT_LOCAL_MODEL = "BAAI/bge-small-en-v1.5"


@runtime_checkable
class Embedder(Protocol):
    name: str
    dim: int

    def encode(self, texts: list[str], is_query: bool = False) -> np.ndarray:
        ...


def _normalize(mat: np.ndarray) -> np.ndarray:
    mat = mat.astype(np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


class FakeEmbedder:
    """Deterministic hash-based embedder for tests (offline, instant)."""

    def __init__(self, dim: int = 128):
        self.dim = dim
        self.name = f"fake-{dim}"

    def encode(self, texts: list[str], is_query: bool = False) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in t.lower().split():
                h = int(hashlib.sha1(tok.encode()).hexdigest(), 16)
                out[i, h % self.dim] += 1.0
        return _normalize(out)


def make_embedder(spec: str | None = None) -> Embedder | None:
    spec = spec or os.environ.get("HICAR_MCP_EMBEDDER")
    if spec == "fake":
        return FakeEmbedder()
    if spec and (spec.startswith("voyage:") or spec.startswith("openai:")):
        from .api import make_api_embedder
        return make_api_embedder(spec)
    # API auto-detect (only if a key is present)
    if spec is None and (os.environ.get("VOYAGE_API_KEY") or os.environ.get("OPENAI_API_KEY")):
        from .api import make_api_embedder
        emb = make_api_embedder(None)
        if emb is not None:
            return emb
    # Local (default, offline)
    model = DEFAULT_LOCAL_MODEL
    if spec and spec.startswith("local:"):
        model = spec.split(":", 1)[1]
    elif spec:
        model = spec
    try:
        from .local import LocalEmbedder
        return LocalEmbedder(model)
    except ImportError:
        return None
