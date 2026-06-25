"""Local, offline embedder backed by sentence-transformers.

Requires the ``semantic`` extra. The default model (BAAI/bge-small-en-v1.5)
downloads once to the HuggingFace cache and is fully offline thereafter
(honors ``HF_HOME`` / ``SENTENCE_TRANSFORMERS_HOME``).
"""

from __future__ import annotations

import numpy as np

# bge models want a retrieval instruction prepended to *queries* only.
_BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class LocalEmbedder:
    def __init__(self, model_name: str):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:  # surfaced to make_embedder -> None
            raise ImportError(
                "sentence-transformers not installed; install hicar-mcp[semantic]"
            ) from e
        self.name = model_name
        self._model = SentenceTransformer(model_name)
        self.dim = int(self._model.get_sentence_embedding_dimension())

    def encode(self, texts: list[str], is_query: bool = False) -> np.ndarray:
        if is_query and "bge" in self.name.lower():
            texts = [_BGE_QUERY_PREFIX + t for t in texts]
        vecs = self._model.encode(
            texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
        )
        return vecs.astype(np.float32)
