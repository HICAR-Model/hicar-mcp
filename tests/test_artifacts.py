"""Artifact write/load round-trip and version gating."""

from __future__ import annotations

import json

import pytest

from hicar_mcp.artifacts.loader import (
    ArtifactVersionMismatch,
    ArtifactsUnavailable,
    load_bundled,
)


def test_roundtrip_preserves_everything(kn_live, kn_bundled):
    assert len(kn_bundled.schema.options) == len(kn_live.schema.options)
    assert len(kn_bundled.schemes) == len(kn_live.schemes)
    assert len(kn_bundled.variables) == len(kn_live.variables)
    assert kn_bundled.docs.keys() == kn_live.docs.keys()
    mp = kn_bundled.get_option("mp")
    assert {(e.name, e.code) for e in mp.enum_values} >= {("morrison", 3), ("thompson", 1)}
    assert kn_bundled.get_variable("pressure").units == "Pa"
    assert kn_bundled.schema.block_for("mp") == "physics"


def test_missing_artifacts_raises(tmp_path):
    with pytest.raises(ArtifactsUnavailable):
        load_bundled(tmp_path)


def test_version_mismatch_raises(bundled_dir):
    v = json.loads((bundled_dir / "version.json").read_text())
    v["artifact_schema"] = "v0-ancient"
    (bundled_dir / "version.json").write_text(json.dumps(v))
    with pytest.raises(ArtifactVersionMismatch):
        load_bundled(bundled_dir)
