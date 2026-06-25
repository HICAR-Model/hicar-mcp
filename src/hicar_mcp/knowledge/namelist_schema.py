"""Merge source + doc into the canonical, queryable namelist schema."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..models import EnumValue, NmlOption, NmlType
from .constants import resolve_int
from .fortran import quoted_strings
from .namelist_doc import clean_description
from .namelist_source import RawCase

_BOOL_LITERALS = {".true.", ".false.", ".t.", ".f."}
_TRIM_STR = re.compile(r"trim\(str\((k\w+)\)\)")


def _resolve_float(token: str | None, constants: dict[str, int]) -> float | None:
    if token is None:
        return None
    token = token.strip()
    try:
        return float(token)
    except ValueError:
        v = constants.get(token)
        return float(v) if v is not None else None


def resolve_val_keys(tokens: list[str], constants: dict[str, int]) -> list[EnumValue]:
    """Resolve interleaved (name, code) ``val_keys`` tokens into EnumValues."""
    items: list[tuple[str, object, str | None]] = []
    for tok in tokens:
        mt = _TRIM_STR.fullmatch(tok.strip())
        if mt:
            items.append(("code", constants.get(mt.group(1)), mt.group(1)))
            continue
        qs = quoted_strings(tok)
        if qs:
            v = qs[0]
            if re.fullmatch(r"-?\d+", v):
                items.append(("code", int(v), None))
            else:
                items.append(("name", v, None))
            continue
        if re.fullmatch(r"-?\d+", tok.strip()):
            items.append(("code", int(tok.strip()), None))
            continue
        items.append(("name", tok.strip(), None))

    result: list[EnumValue] = []
    pending: str | None = None
    for kind, val, const in items:
        if kind == "name":
            if pending is not None:
                result.append(EnumValue(name=pending))
            pending = str(val)
        else:
            result.append(EnumValue(name=pending, code=val, constant=const))
            pending = None
    if pending is not None:
        result.append(EnumValue(name=pending))
    return result


def _infer_type(opt: NmlOption) -> NmlType:
    if opt.enum_values:
        named = [e for e in opt.enum_values if e.name and not re.fullmatch(r"-?\d+", e.name)]
        return NmlType.STRING_ENUM if named else NmlType.INT_ENUM
    if opt.int_values:
        return NmlType.INT_ENUM
    if opt.name.lower().endswith("_date"):
        return NmlType.DATE
    d = opt.default.strip()
    if d.lower() in _BOOL_LITERALS:
        return NmlType.BOOL
    if "," in d:
        return NmlType.ARRAY
    if re.fullmatch(r"-?\d+", d):
        return NmlType.INT
    if re.fullmatch(r"-?\d*\.\d+([eE][+-]?\d+)?|-?\d+\.\d*", d):
        return NmlType.FLOAT
    if d == "" and opt.minimum is None and opt.maximum is None:
        return NmlType.STRING if not opt.dimensions else NmlType.ARRAY
    if (opt.minimum is not None or opt.maximum is not None) and d == "":
        return NmlType.FLOAT
    return NmlType.STRING


@dataclass
class NamelistSchema:
    options: dict[str, NmlOption] = field(default_factory=dict)
    group_blocks: dict[str, str] = field(default_factory=dict)  # group -> &block
    block_vars: dict[str, list[str]] = field(default_factory=dict)  # &block -> [vars]

    @property
    def block_groups(self) -> dict[str, str]:
        return {b: g for g, b in self.group_blocks.items()}

    @property
    def groups(self) -> list[str]:
        seen = []
        for o in self.options.values():
            if o.group and o.group not in seen:
                seen.append(o.group)
        return seen

    def get(self, name: str) -> NmlOption | None:
        if name in self.options:
            return self.options[name]
        low = name.lower()
        for k, v in self.options.items():
            if k.lower() == low:
                return v
        return None

    def block_for(self, name: str) -> str | None:
        opt = self.get(name)
        if opt is None:
            return None
        return self.group_blocks.get(opt.group, opt.group.lower())

    def options_in_group(self, group: str) -> list[NmlOption]:
        return [o for o in self.options.values() if o.group.lower() == group.lower()]

    def search(self, query: str, group: str | None = None) -> list[NmlOption]:
        q = query.lower()
        hits = []
        for o in self.options.values():
            if group and o.group.lower() != group.lower():
                continue
            hay = f"{o.name} {o.group} {o.description}".lower()
            if q in hay:
                # rank: name match first
                score = (0 if q in o.name.lower() else 1, o.name)
                hits.append((score, o))
        hits.sort(key=lambda x: x[0])
        return [o for _, o in hits]


def build_schema(
    raw: dict[str, RawCase],
    group_blocks: dict[str, str],
    block_vars: dict[str, list[str]],
    constants: dict[str, int],
    doc: dict[str, dict] | None = None,
) -> NamelistSchema:
    schema = NamelistSchema(group_blocks=dict(group_blocks), block_vars=dict(block_vars))
    doc = doc or {}

    for name, rc in raw.items():
        opt = NmlOption(
            name=name,
            group=rc.group,
            fortran_block=group_blocks.get(rc.group, rc.group.lower()),
            description=rc.description,
            units=rc.units,
            default=rc.default,
            nest_semantics=rc.type,
        )
        # HICAR initializes min=max=0; a case sets one/both. Interpret that:
        #   (0,0)        -> no constraints (the sentinel)
        #   max == 0     -> no upper bound (HICAR has no genuine max-of-zero)
        mn = _resolve_float(rc.min_token, constants)
        mx = _resolve_float(rc.max_token, constants)
        mn = 0.0 if mn is None else mn
        mx = 0.0 if mx is None else mx
        active = not (mn == 0 and mx == 0)
        opt.minimum = mn if active else None
        opt.maximum = mx if (active and mx != 0) else None
        opt.enum_values = resolve_val_keys(rc.val_keys_tokens, constants)
        if rc.values_tokens:
            opt.int_values = [
                v for v in (resolve_int(t, constants) for t in rc.values_tokens) if v is not None
            ]
        # doc enrichment where source is silent
        d = doc.get(name)
        if d:
            opt.source = "both"
            if not opt.description and d.get("description"):
                opt.description = clean_description(d["description"])
            if not opt.units and d.get("units"):
                opt.units = d["units"]
        opt.inferred_type = _infer_type(opt)
        schema.options[name] = opt

    # Add variables that appear in a namelist /block/ but lack metadata,
    # so validation does not flag them as unknown.
    bg = schema.block_groups
    for block, vars_ in block_vars.items():
        for v in vars_:
            if schema.get(v) is None:
                schema.options[v] = NmlOption(
                    name=v,
                    group=bg.get(block, block),
                    fortran_block=block,
                    source="block",
                    notes=["declared in namelist block but no get_nml_var_metadata entry"],
                )
    return schema
