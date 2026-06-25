"""Build the physics-scheme registry from the namelist schema.

Each scheme *selector* option (``mp``, ``pbl``, ...) carries an enum of
choices in its ``val_keys``; this module turns those into ``Scheme`` records,
attaching per-choice descriptions and a "supported" flag scraped from the
option's description (lines marked ``(NOT SUPPORTED)``).
"""

from __future__ import annotations

import re

from ..models import NmlOption, Scheme

# namelist selector option -> human category name
SELECTOR_CATEGORY = {
    "mp": "microphysics",
    "pbl": "pbl",
    "lsm": "land_surface",
    "rad": "radiation",
    "conv": "cumulus",
    "water": "water",
    "wind": "wind",
    "adv": "advection",
    "sfc": "surface_layer",
    "sm": "snow",
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _description_index(description: str) -> dict[str, tuple[bool, str]]:
    """Map normalized choice token -> (supported, line) from a description."""
    idx: dict[str, tuple[bool, str]] = {}
    for line in description.splitlines():
        m = re.search(r"'([^']+)'", line)
        if not m:
            continue
        supported = "NOT SUPPORTED" not in line.upper()
        idx[_norm(m.group(1))] = (supported, line.strip())
    return idx


def build_scheme_registry(options: dict[str, NmlOption]) -> list[Scheme]:
    schemes: list[Scheme] = []
    for selector, category in SELECTOR_CATEGORY.items():
        opt = options.get(selector)
        if opt is None or not opt.enum_values:
            continue
        desc_idx = _description_index(opt.description)
        for ev in opt.enum_values:
            if ev.name is None:
                continue
            if ev.name.lower() == "none" or ev.code == 0:
                continue  # "no scheme" sentinel
            supported, line = desc_idx.get(_norm(ev.name), (True, ""))
            schemes.append(
                Scheme(
                    category=category,
                    selector=selector,
                    name=ev.name,
                    code=ev.code,
                    constant=ev.constant,
                    supported=supported,
                    description=line,
                )
            )
    return schemes


def categories(schemes: list[Scheme]) -> list[str]:
    seen: list[str] = []
    for s in schemes:
        if s.category not in seen:
            seen.append(s.category)
    return seen
