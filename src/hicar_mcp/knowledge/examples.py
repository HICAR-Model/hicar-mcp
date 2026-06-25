"""Load example namelists (from a HICAR checkout, or bundled copies)."""

from __future__ import annotations

from pathlib import Path


def load_examples(dirs: list[Path]) -> dict[str, str]:
    """Return {filename: content} for every ``*.nml`` under the given dirs."""
    out: dict[str, str] = {}
    for d in dirs:
        if not d or not d.exists():
            continue
        for p in sorted(d.glob("*.nml")):
            try:
                out[p.name] = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    return out
