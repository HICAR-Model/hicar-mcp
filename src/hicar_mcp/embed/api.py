"""Optional API embedders (Voyage / OpenAI).

Used only for *live* index rebuilds where higher retrieval quality is wanted;
the bundled index is always built with the local model, so API embedders
cannot query it (different vector space).
"""

from __future__ import annotations

import os

import numpy as np

from .base import _normalize


class _VoyageEmbedder:
    def __init__(self, model: str):
        import voyageai  # noqa: F401
        self._vo = voyageai.Client()
        self.name = f"voyage:{model}"
        self.model = model
        self.dim = 1024  # voyage-code-2 default; refined after first call

    def encode(self, texts: list[str], is_query: bool = False) -> np.ndarray:
        kind = "query" if is_query else "document"
        res = self._vo.embed(texts, model=self.model, input_type=kind)
        mat = np.array(res.embeddings, dtype=np.float32)
        self.dim = mat.shape[1]
        return _normalize(mat)


class _OpenAIEmbedder:
    def __init__(self, model: str):
        from openai import OpenAI
        self._client = OpenAI()
        self.name = f"openai:{model}"
        self.model = model
        self.dim = 1536

    def encode(self, texts: list[str], is_query: bool = False) -> np.ndarray:
        res = self._client.embeddings.create(model=self.model, input=texts)
        mat = np.array([d.embedding for d in res.data], dtype=np.float32)
        self.dim = mat.shape[1]
        return _normalize(mat)


def make_api_embedder(spec: str | None):
    try:
        if spec and spec.startswith("voyage:"):
            return _VoyageEmbedder(spec.split(":", 1)[1])
        if spec and spec.startswith("openai:"):
            return _OpenAIEmbedder(spec.split(":", 1)[1])
        if os.environ.get("VOYAGE_API_KEY"):
            return _VoyageEmbedder("voyage-code-2")
        if os.environ.get("OPENAI_API_KEY"):
            return _OpenAIEmbedder("text-embedding-3-small")
    except Exception:  # noqa: BLE001 - any client init failure -> fall back
        return None
    return None
