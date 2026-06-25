"""Parse integer constants and the ``kVARS`` enum from ``icar_constants.F90``.

* ``parse_k_constants`` -> {"kMP_MORRISON": 3, ...} -- used to resolve the
  ``trim(str(kXXX))`` codes embedded in namelist ``val_keys``.
* ``parse_kvars`` -> ["u", "v", "w", ...] -- the ordered list of model
  variable enum members.
"""

from __future__ import annotations

import re

# integer[, parameter] :: kNAME = <int>
_KCONST = re.compile(
    r"^\s*integer\s*(?:,\s*parameter\s*)?::\s*(k\w+)\s*=\s*(-?\d+)",
    re.IGNORECASE,
)


def parse_k_constants(text: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for line in text.splitlines():
        m = _KCONST.match(line)
        if m:
            out[m.group(1)] = int(m.group(2))
    return out


def parse_kvars(text: str) -> list[str]:
    """Ordered ``kVARS`` member names from the ``var_constants_type`` block."""
    # Locate the derived type definition.
    start = re.search(r"type\b[^\n]*\bvar_constants_type\b", text, re.IGNORECASE)
    if not start:
        return []
    rest = text[start.end():]
    end = re.search(r"\bend\s+type\b", rest, re.IGNORECASE)
    block = rest[: end.start()] if end else rest

    members: list[str] = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line or line.startswith("!"):
            continue
        m = re.match(r"integer\s*(?:,[^:]*)?::\s*(.+)$", line, re.IGNORECASE)
        if not m:
            continue
        decl = m.group(1).split("!")[0]
        for name in decl.split(","):
            name = name.strip()
            # drop any kind/dim suffix and the sentinel
            name = re.split(r"[\s(=]", name)[0]
            if name and name.lower() != "last_var" and re.match(r"^\w+$", name):
                members.append(name)
    return members


def resolve_int(token: str, constants: dict[str, int]) -> int | None:
    """Resolve an integer literal or a known ``k*`` constant name."""
    token = token.strip()
    if re.fullmatch(r"-?\d+", token):
        return int(token)
    return constants.get(token)
