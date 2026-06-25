"""(De)serialization of the v1 bundled-artifact set.

Artifact files (under ``hicar_mcp/data``):

* ``version.json``    -- provenance + schema version
* ``schema.json``     -- namelist schema (groups, blocks, options)
* ``schemes.json``    -- physics scheme registry
* ``variables.json``  -- kVARS model-variable catalog
* ``kvars.json``      -- ordered kVARS member names
* ``docs/*.md`` + ``docs_index.json``  -- documentation pages
* ``examples/*.nml``  -- example namelists
* ``index/``          -- semantic index (separate module)
"""

from __future__ import annotations

from ..models import ModelVar, NmlOption, Scheme
from ..knowledge.namelist_schema import NamelistSchema


def dump_schema(schema: NamelistSchema) -> dict:
    return {
        "group_blocks": schema.group_blocks,
        "block_vars": schema.block_vars,
        "options": [o.to_dict() for o in schema.options.values()],
    }


def load_schema(d: dict) -> NamelistSchema:
    schema = NamelistSchema(
        group_blocks=d.get("group_blocks", {}),
        block_vars=d.get("block_vars", {}),
    )
    for od in d.get("options", []):
        opt = NmlOption.from_dict(od)
        schema.options[opt.name] = opt
    return schema


def dump_schemes(schemes: list[Scheme]) -> list[dict]:
    return [s.to_dict() for s in schemes]


def load_schemes(data: list[dict]) -> list[Scheme]:
    return [Scheme.from_dict(s) for s in data]


def dump_variables(variables: list[ModelVar]) -> list[dict]:
    return [v.to_dict() for v in variables]


def load_variables(data: list[dict]) -> list[ModelVar]:
    return [ModelVar.from_dict(v) for v in data]
