"""Regenerate bundled artifacts (structured knowledge + semantic index).

Run in CI on each HICAR release (see ``scripts/regenerate.py``), or locally via
``hicar-mcp regenerate --repo /path/to/HICAR``.
"""

from __future__ import annotations

from pathlib import Path

from .codesearch.semantic import SemanticIndex, chunk_repo, corpus_hash
from .config import bundled_data_dir
from .embed.base import make_embedder
from .extract.runner import extract_from_repo, write_artifacts


def regenerate(
    repo: Path,
    out_dir: Path | None = None,
    commit: str | None = None,
    built_at: str | None = None,
    build_embeddings: bool = True,
    embedder_spec: str | None = None,
) -> dict:
    out_dir = out_dir or bundled_data_dir()
    kn = extract_from_repo(repo, mode="bundled")
    write_artifacts(
        kn, out_dir,
        hicar_version_str=kn.version.get("hicar_version"),
        hicar_commit=commit, built_at=built_at,
    )
    summary = {
        "out_dir": str(out_dir),
        "options": len(kn.schema.options),
        "schemes": len(kn.schemes),
        "variables": len(kn.variables),
        "docs": len(kn.docs),
        "examples": len(kn.examples),
        "hicar_version": kn.version.get("hicar_version"),
        "embeddings": None,
    }
    if build_embeddings:
        emb = make_embedder(embedder_spec)
        if emb is None:
            summary["embeddings"] = "skipped (no embedder; install hicar-mcp[semantic])"
        else:
            chunks = chunk_repo(repo)
            idx = SemanticIndex.build(chunks, emb, corpus_hash_=corpus_hash(repo), built_at=built_at)
            idx.save(out_dir / "index")
            summary["embeddings"] = {"backend": emb.name, "chunks": len(chunks)}
    return summary
