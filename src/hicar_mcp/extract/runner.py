"""Parse a HICAR checkout into a ``Knowledge`` object and/or write artifacts."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from .. import ARTIFACT_SCHEMA_VERSION
from ..config import (
    CONSTANTS,
    DOCS_DIR,
    EXAMPLES_DIR,
    MKDOCS,
    NAMELIST_DOC,
    NAMELIST_UTIL,
    OUTPUT_META,
    TEST_INPUT_DIR,
)
from ..artifacts import schema_v1
from ..docs.markdown import load_docs
from ..kb import Knowledge
from ..knowledge import constants, namelist_doc, namelist_schema, namelist_source, varcatalog
from ..knowledge.examples import load_examples
from ..knowledge.schemes import build_scheme_registry

OPTIONS_OBJ = "src/objects/options_obj.F90"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def hicar_version(constants_text: str) -> str:
    m = re.search(r'kVERSION_STRING\s*=\s*"([^"]*)"', constants_text)
    return m.group(1) if m else "unknown"


def extract_from_repo(repo_root: Path, mode: str = "live") -> Knowledge:
    nml_util = _read(repo_root / NAMELIST_UTIL)
    consts_txt = _read(repo_root / CONSTANTS)
    options_txt = _read(repo_root / OPTIONS_OBJ)
    outmeta_txt = _read(repo_root / OUTPUT_META)

    kconsts = constants.parse_k_constants(consts_txt)
    kvars = constants.parse_kvars(consts_txt)
    raw = namelist_source.parse_metadata(nml_util)
    gblocks = namelist_source.parse_group_blocks(nml_util)
    nblocks = namelist_source.parse_namelist_blocks(options_txt)

    doc_path = repo_root / NAMELIST_DOC
    doc = namelist_doc.parse_doc(_read(doc_path)) if doc_path.exists() else None

    schema = namelist_schema.build_schema(raw, gblocks, nblocks, kconsts, doc)
    scheme_list = build_scheme_registry(schema.options)
    variables = varcatalog.parse_varcatalog(outmeta_txt)

    docs = load_docs(repo_root / DOCS_DIR, repo_root / MKDOCS)
    examples = load_examples([repo_root / EXAMPLES_DIR, repo_root / TEST_INPUT_DIR])

    version = {
        "artifact_schema": ARTIFACT_SCHEMA_VERSION,
        "hicar_version": hicar_version(consts_txt),
        "hicar_commit": None,
        "built_at": None,
        "source": "live",
    }
    return Knowledge(
        schema=schema,
        schemes=scheme_list,
        variables=variables,
        kvars=kvars,
        docs=docs,
        examples=examples,
        version=version,
        mode=mode,
    )


def write_artifacts(
    kn: Knowledge,
    out_dir: Path,
    hicar_version_str: str | None = None,
    hicar_commit: str | None = None,
    built_at: str | None = None,
) -> None:
    """Serialize a Knowledge object into the bundled-artifact directory."""
    out_dir.mkdir(parents=True, exist_ok=True)
    version = dict(kn.version)
    version.update(
        {
            "artifact_schema": ARTIFACT_SCHEMA_VERSION,
            "source": "bundled",
            "hicar_version": hicar_version_str or version.get("hicar_version", "unknown"),
            "hicar_commit": hicar_commit,
            "built_at": built_at,
        }
    )

    def _w(name: str, obj) -> None:
        (out_dir / name).write_text(json.dumps(obj, indent=2), encoding="utf-8")

    _w("version.json", version)
    _w("schema.json", schema_v1.dump_schema(kn.schema))
    _w("schemes.json", schema_v1.dump_schemes(kn.schemes))
    _w("variables.json", schema_v1.dump_variables(kn.variables))
    _w("kvars.json", kn.kvars)

    docs_dir = out_dir / "docs"
    if docs_dir.exists():
        shutil.rmtree(docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)
    docs_index = {}
    for page in kn.docs.values():
        (docs_dir / page.name).write_text(page.text, encoding="utf-8")
        docs_index[page.name] = {"title": page.title, "order": page.order}
    _w("docs_index.json", docs_index)

    ex_dir = out_dir / "examples"
    if ex_dir.exists():
        shutil.rmtree(ex_dir)
    ex_dir.mkdir(parents=True, exist_ok=True)
    for name, content in kn.examples.items():
        (ex_dir / name).write_text(content, encoding="utf-8")
