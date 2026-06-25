"""Load bundled artifacts into a ``Knowledge`` object."""

from __future__ import annotations

import json
from pathlib import Path

from .. import ARTIFACT_SCHEMA_VERSION
from ..kb import DocPage, Knowledge, slug_to_title
from . import schema_v1


class ArtifactsUnavailable(RuntimeError):
    """Raised when bundled artifacts are missing or unreadable."""


class ArtifactVersionMismatch(RuntimeError):
    """Raised when bundled artifacts use an incompatible schema version."""


def artifacts_present(data_dir: Path) -> bool:
    return (data_dir / "version.json").exists() and (data_dir / "schema.json").exists()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_bundled(data_dir: Path) -> Knowledge:
    if not artifacts_present(data_dir):
        raise ArtifactsUnavailable(
            f"No bundled artifacts found in {data_dir}. Either set HICAR_REPO to a HICAR "
            f"checkout (live mode), or regenerate artifacts with `hicar-mcp regenerate`."
        )
    version = _load_json(data_dir / "version.json")
    got = version.get("artifact_schema")
    if got != ARTIFACT_SCHEMA_VERSION:
        raise ArtifactVersionMismatch(
            f"Bundled artifacts use schema {got!r} but this package expects "
            f"{ARTIFACT_SCHEMA_VERSION!r}. Upgrade hicar-mcp or regenerate artifacts."
        )

    schema = schema_v1.load_schema(_load_json(data_dir / "schema.json"))
    schemes = schema_v1.load_schemes(_load_json(data_dir / "schemes.json"))
    variables = schema_v1.load_variables(_load_json(data_dir / "variables.json"))
    kvars = _load_json(data_dir / "kvars.json") if (data_dir / "kvars.json").exists() else []

    docs: dict[str, DocPage] = {}
    docs_dir = data_dir / "docs"
    docs_index = {}
    if (data_dir / "docs_index.json").exists():
        docs_index = _load_json(data_dir / "docs_index.json")
    if docs_dir.exists():
        for p in sorted(docs_dir.glob("*.md")):
            meta = docs_index.get(p.name, {})
            docs[p.name] = DocPage(
                name=p.name,
                title=meta.get("title", slug_to_title(p.name)),
                text=p.read_text(encoding="utf-8", errors="replace"),
                order=meta.get("order", 1000),
            )

    examples: dict[str, str] = {}
    ex_dir = data_dir / "examples"
    if ex_dir.exists():
        for p in sorted(ex_dir.glob("*.nml")):
            examples[p.name] = p.read_text(encoding="utf-8", errors="replace")

    return Knowledge(
        schema=schema,
        schemes=schemes,
        variables=variables,
        kvars=kvars,
        docs=docs,
        examples=examples,
        version=version,
        mode="bundled",
    )
