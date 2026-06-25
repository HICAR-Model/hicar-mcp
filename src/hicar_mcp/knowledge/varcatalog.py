"""Parse the kVARS model-variable catalog from ``get_varmeta``.

``get_varmeta`` is a long ``if (var_idx==kVARS%x) ... else if ...`` chain.
Each branch sets ``var_meta%name``, optional ``%minval``/``%maxval``,
``%dimensions`` (a symbolic constant) and an ``%attributes`` array of
``attribute_t("key","value")`` pairs, plus an optional forcing hook
``forcing_var = (opt%forcing%<x> /= "")``.
"""

from __future__ import annotations

import re

from ..models import ModelVar
from .fortran import join_continuations, strip_inline_comment

_BRANCH = re.compile(r"(?:else\s+)?if\s*\(\s*var_idx\s*==\s*kVARS%(\w+)\s*\)\s*then", re.I)
_ATTR = re.compile(r'attribute_t\(\s*"([^"]*)"\s*,\s*"([^"]*)"\s*\)')
_FORCING = re.compile(r"opt%forcing%(\w+)\s*/=")


def _value_after_eq(line: str) -> str:
    return line.split("=", 1)[1].strip() if "=" in line else ""


def _to_float(tok: str) -> float | None:
    try:
        return float(tok)
    except ValueError:
        return None


def parse_varcatalog(text: str) -> list[ModelVar]:
    lines = join_continuations(text)
    # find branch boundaries
    bounds: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = _BRANCH.search(line)
        if m:
            bounds.append((i, m.group(1)))
    out: list[ModelVar] = []
    for idx, (start, kvar) in enumerate(bounds):
        end = bounds[idx + 1][0] if idx + 1 < len(bounds) else len(lines)
        block = lines[start:end]
        mv = ModelVar(kvar=kvar, name="")
        attrs: dict[str, str] = {}
        for raw in block:
            line = strip_inline_comment(raw)
            if "var_meta%name" in line:
                m = re.search(r'"([^"]*)"', line)
                if m:
                    mv.name = m.group(1)
            elif "var_meta%minval" in line:
                mv.minval = _to_float(_value_after_eq(line))
            elif "var_meta%maxval" in line:
                mv.maxval = _to_float(_value_after_eq(line))
            elif "var_meta%dimensions" in line:
                rhs = _value_after_eq(line)
                m = re.match(r"(\w+)", rhs)
                if m:
                    mv.dimensions = m.group(1)
            if "attribute_t" in line:
                for k, v in _ATTR.findall(line):
                    attrs[k] = v  # last wins (handles duplicate long_name)
            fm = _FORCING.search(line)
            if fm:
                mv.has_forcing_hook = True
                mv.forcing_option = fm.group(1)
        mv.standard_name = attrs.get("standard_name", "")
        mv.long_name = attrs.get("long_name", "")
        mv.units = attrs.get("units", "")
        mv.description = attrs.get("description", "")
        if mv.name:
            out.append(mv)
    return out
