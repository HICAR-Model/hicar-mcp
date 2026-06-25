"""PRIMARY namelist parser: extract option metadata from HICAR source.

Source of truth is ``get_nml_var_metadata`` in ``namelist_utilities.F90`` (a
large ``select case (name)``). We also parse:

* ``write_group_header`` -> logical-group -> ``&block`` name mapping, and
* the ``namelist /block/ var, ...`` declarations in ``options_obj.F90`` -> the
  authoritative set of variables belonging to each ``&block``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .fortran import (
    description_from_assignment,
    extract_subroutine,
    join_continuations,
    quoted_strings,
    split_top_level,
    strip_inline_comment,
)

_CASE = re.compile(r'^\s*case\s*\((\s*"(?:[^"]|"")*"(?:\s*,\s*"(?:[^"]|"")*")*\s*)\)', re.I)
_ASSIGN = re.compile(r"^\s*(\w+)\s*=\s*(.*)$")
_ARRAY_BODY = re.compile(r"\[(?:[^\]]*::)?\s*(.*?)\s*\]", re.S)


@dataclass
class RawCase:
    name: str
    group: str = ""
    description: str = ""
    default: str = ""
    units: str = ""
    type: int = 0
    min_token: str | None = None
    max_token: str | None = None
    val_keys_tokens: list[str] = field(default_factory=list)
    values_tokens: list[str] = field(default_factory=list)


def _array_tokens(rhs: str) -> list[str]:
    m = _ARRAY_BODY.search(rhs)
    if not m:
        return []
    return [t.strip() for t in split_top_level(m.group(1)) if t.strip()]


def parse_metadata(text: str) -> dict[str, RawCase]:
    """Parse ``get_nml_var_metadata`` into {option_name: RawCase}."""
    body = extract_subroutine(text, "get_nml_var_metadata")
    if body is None:
        return {}
    lines = join_continuations(body)

    blocks: dict[str, list[str]] = {}
    current: list[str] = []
    for line in lines:
        cm = _CASE.match(line)
        if cm:
            current = quoted_strings(cm.group(1))
            for n in current:
                blocks.setdefault(n, [])
            continue
        stripped = line.strip().lower()
        if stripped.startswith(("select case", "end select", "case default", "case default")):
            current = []
            continue
        for n in current:
            blocks[n].append(line)

    out: dict[str, RawCase] = {}
    for name, blines in blocks.items():
        rc = RawCase(name=name)
        for line in blines:
            m = _ASSIGN.match(strip_inline_comment(line))
            if not m:
                continue
            key, rhs = m.group(1).lower(), m.group(2).strip()
            if key == "description":
                rc.description = description_from_assignment(rhs)
            elif key == "default":
                qs = quoted_strings(rhs)
                rc.default = qs[0] if qs else rhs.strip()
            elif key == "group":
                qs = quoted_strings(rhs)
                rc.group = qs[0] if qs else rhs.strip()
            elif key == "units":
                qs = quoted_strings(rhs)
                rc.units = qs[0] if qs else rhs.strip()
            elif key == "type":
                try:
                    rc.type = int(rhs)
                except ValueError:
                    pass
            elif key == "min":
                rc.min_token = rhs
            elif key == "max":
                rc.max_token = rhs
            elif key == "val_keys":
                rc.val_keys_tokens = _array_tokens(rhs)
            elif key == "values":
                rc.values_tokens = _array_tokens(rhs)
        out[name] = rc
    return out


def parse_group_blocks(text: str) -> dict[str, str]:
    """logical group ("MP_Parameters") -> namelist &block ("mp_parameters")."""
    body = extract_subroutine(text, "write_group_header")
    mapping: dict[str, str] = {}
    if body is None:
        return mapping
    current_group: str | None = None
    for line in join_continuations(body):
        cm = re.search(r'case\s*\(\s*"([^"]+)"\s*\)', line)
        if cm:
            current_group = cm.group(1)
            continue
        bm = re.search(r'"&(\w+)"', line)
        if bm and current_group:
            mapping[current_group] = bm.group(1)
            current_group = None
    return mapping


def parse_namelist_blocks(options_text: str) -> dict[str, list[str]]:
    """Parse ``namelist /block/ v1, v2, ...`` -> {block: [vars]}."""
    out: dict[str, list[str]] = {}
    for line in join_continuations(options_text):
        m = re.match(r"\s*namelist\s*/\s*(\w+)\s*/\s*(.+)$", line, re.I)
        if not m:
            continue
        block = m.group(1).lower()
        rhs = strip_inline_comment(m.group(2))
        vars_ = [v.strip() for v in rhs.split(",") if v.strip()]
        out.setdefault(block, [])
        for v in vars_:
            if re.fullmatch(r"\w+", v):
                out[block].append(v)
    return out
