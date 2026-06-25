"""Format values and emit Fortran namelist groups."""

from __future__ import annotations

import re

from ..models import NmlType

_QUOTED_TYPES = {NmlType.STRING, NmlType.STRING_ENUM, NmlType.DATE}


def format_value(value: str, ntype: NmlType) -> str:
    """Render a value for the namelist, quoting strings as needed."""
    v = value.strip()
    if v == "":
        return "''"
    # already quoted?
    if len(v) >= 2 and v[0] in "'\"" and v[-1] == v[0]:
        return f"'{v[1:-1]}'"
    if ntype in _QUOTED_TYPES:
        # numbers/bools that happen to be enum codes stay unquoted
        if ntype in (NmlType.STRING_ENUM,) and re.fullmatch(r"-?\d+", v):
            return v
        return f"'{v}'"
    return v


def emit_group(block: str, lines: list[str]) -> str:
    out = [f"&{block}"]
    out.extend(lines)
    out.append("/")
    return "\n".join(out)
