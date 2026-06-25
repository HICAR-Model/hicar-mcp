"""Lexical (with rg-absent fallback), symbol and semantic search tests."""

from __future__ import annotations

import numpy as np

from hicar_mcp.codesearch import lexical, symbols
from hicar_mcp.codesearch.semantic import SemanticIndex, chunk_repo, corpus_hash, index_is_fresh
from hicar_mcp.embed.base import FakeEmbedder


def test_lexical_python_fallback(monkeypatch, fixtures_repo):
    # force the pure-Python path regardless of whether rg is installed
    monkeypatch.setattr(lexical.shutil, "which", lambda _: None)
    assert not lexical.have_ripgrep()
    hits = lexical.code_search([fixtures_repo / "src"], "mp_step")
    assert any(h.path.endswith("mp_driver.F90") for h in hits)
    assert any("mp_step" in h.text for h in hits)


def test_symbol_index(fixtures_repo):
    idx = symbols.build_symbol_index(fixtures_repo)
    found = symbols.find_symbol(idx, "mp_step")
    assert found and found[0].kind == "subroutine"
    body = symbols.read_symbol(fixtures_repo, found[0])
    assert "mp_step" in body["text"]


def test_safe_path_rejects_escape(fixtures_repo):
    assert symbols.safe_path(fixtures_repo, "../../etc/passwd") is None
    assert symbols.safe_path(fixtures_repo, "src/physics/mp_driver.F90") is not None


def test_semantic_build_search_roundtrip(tmp_path, fixtures_repo):
    chunks = chunk_repo(fixtures_repo)
    assert chunks
    assert any(c.kind == "code" for c in chunks) and any(c.kind == "docs" for c in chunks)
    emb = FakeEmbedder()
    idx = SemanticIndex.build(chunks, emb, corpus_hash_=corpus_hash(fixtures_repo))
    res = idx.search("microphysics scheme", emb, k=3)
    assert res and "score" in res[0]

    # save/load round-trip
    idx.save(tmp_path / "index")
    idx2 = SemanticIndex.load(tmp_path / "index")
    assert idx2.meta.count == idx.meta.count
    assert np.allclose(idx2.embeddings, idx.embeddings)


def test_semantic_staleness(fixtures_repo):
    emb = FakeEmbedder()
    idx = SemanticIndex.build(chunk_repo(fixtures_repo), emb, corpus_hash_=corpus_hash(fixtures_repo))
    assert index_is_fresh(idx.meta, fixtures_repo, emb.name)
    # a different embedder name invalidates the index
    assert not index_is_fresh(idx.meta, fixtures_repo, "other-embedder")


def test_semantic_kind_filter(fixtures_repo):
    emb = FakeEmbedder()
    idx = SemanticIndex.build(chunk_repo(fixtures_repo), emb)
    docs = idx.search("output interval", emb, k=10, kind="docs")
    assert all(r["kind"] == "docs" for r in docs)
