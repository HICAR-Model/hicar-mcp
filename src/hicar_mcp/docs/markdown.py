"""Load the HICAR markdown docs and derive an ordering from ``mkdocs.yml``."""

from __future__ import annotations

import re
from pathlib import Path

from ..kb import DocPage, slug_to_title


def _nav_order(mkdocs_text: str) -> dict[str, tuple[int, str]]:
    """Best-effort parse of the mkdocs ``nav:`` block.

    Returns {filename: (order, title)}. We avoid a YAML dependency and just
    scan ``- Title: file.md`` / ``- file.md`` lines under ``nav:``.
    """
    order: dict[str, tuple[int, str]] = {}
    in_nav = False
    idx = 0
    for raw in mkdocs_text.splitlines():
        if re.match(r"^\s*nav\s*:", raw):
            in_nav = True
            continue
        if in_nav:
            # leaving nav when a new top-level key appears
            if raw and not raw[0].isspace() and ":" in raw and not raw.lstrip().startswith("-"):
                break
            m = re.search(r"-\s*(?:'([^']+)'|\"([^\"]+)\"|([^:]+?))\s*:\s*([^\s]+\.md)\s*$", raw)
            if m:
                title = (m.group(1) or m.group(2) or m.group(3) or "").strip()
                fname = m.group(4).strip()
                order[fname] = (idx, title or slug_to_title(fname))
                idx += 1
                continue
            m2 = re.search(r"-\s*([^\s].*\.md)\s*$", raw)
            if m2:
                fname = m2.group(1).strip()
                order[fname] = (idx, slug_to_title(fname))
                idx += 1
    return order


def load_docs(docs_dir: Path | None, mkdocs_path: Path | None = None) -> dict[str, DocPage]:
    if not docs_dir or not docs_dir.exists():
        return {}
    nav = {}
    if mkdocs_path and mkdocs_path.exists():
        try:
            nav = _nav_order(mkdocs_path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            nav = {}
    pages: dict[str, DocPage] = {}
    for p in sorted(docs_dir.glob("*.md")):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        order, title = nav.get(p.name, (1000, slug_to_title(p.name)))
        pages[p.name] = DocPage(name=p.name, title=title, text=text, order=order)
    return pages
