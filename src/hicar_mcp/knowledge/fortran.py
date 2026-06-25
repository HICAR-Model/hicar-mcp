"""Small, dependency-free helpers for chewing on free-form Fortran (.F90).

These are deliberately lenient line/token utilities rather than a real Fortran
parser -- they only need to cope with the very regular code in HICAR's
metadata routines (``get_nml_var_metadata``, ``get_varmeta``).
"""

from __future__ import annotations

import re

_TRAIL_COMMENT = re.compile(r"&\s*(?:!.*)?$")
_QUOTED = re.compile(r'"((?:[^"]|"")*)"')


def strip_inline_comment(line: str) -> str:
    """Remove a trailing ``! comment`` that is not inside a quoted string."""
    out = []
    in_s = in_d = False
    i = 0
    while i < len(line):
        c = line[i]
        if c == "'" and not in_d:
            in_s = not in_s
        elif c == '"' and not in_s:
            in_d = not in_d
        elif c == "!" and not in_s and not in_d:
            break
        out.append(c)
        i += 1
    return "".join(out)


def join_continuations(text: str) -> list[str]:
    """Collapse Fortran ``&`` line continuations into single logical lines.

    A physical line whose last non-comment token is ``&`` continues onto the
    next; a leading ``&`` on the continuation is dropped. Quoted ``//`` string
    concatenation (as used in the metadata descriptions) is preserved verbatim
    so the caller can extract the quoted segments.
    """
    logical: list[str] = []
    buf = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        cont = bool(_TRAIL_COMMENT.search(line))
        # strip a trailing '&' (and any comment after it)
        core = _TRAIL_COMMENT.sub("", line) if cont else line
        if buf:
            core = core.lstrip()
            # drop a leading continuation ampersand
            if core.startswith("&"):
                core = core[1:]
        buf += core
        if cont:
            continue
        logical.append(buf)
        buf = ""
    if buf:
        logical.append(buf)
    return logical


def quoted_strings(s: str) -> list[str]:
    """Return the contents of every double-quoted literal in ``s``, in order."""
    return [m.group(1).replace('""', '"') for m in _QUOTED.finditer(s)]


def description_from_assignment(rhs: str) -> str:
    """Reconstruct a (possibly multi-line) description string.

    HICAR builds multi-line descriptions as
    ``"line1"//achar(10)//BLNK_CHR_N//"line2"//...``. We join the quoted
    segments with newlines and tidy whitespace.
    """
    segs = quoted_strings(rhs)
    if not segs:
        return ""
    cleaned = [s.strip() for s in segs]
    return "\n".join(cleaned).strip()


def split_top_level(s: str, sep: str = ",") -> list[str]:
    """Split on ``sep`` ignoring separators inside (), [] or quotes."""
    parts: list[str] = []
    depth = 0
    in_s = in_d = False
    cur = ""
    for c in s:
        if c == "'" and not in_d:
            in_s = not in_s
        elif c == '"' and not in_s:
            in_d = not in_d
        if not in_s and not in_d:
            if c in "([":
                depth += 1
            elif c in ")]":
                depth -= 1
            elif c == sep and depth == 0:
                parts.append(cur)
                cur = ""
                continue
        cur += c
    if cur.strip() or parts:
        parts.append(cur)
    return parts


def extract_subroutine(text: str, name: str) -> str | None:
    """Return the body text of ``subroutine name`` ... ``end subroutine``."""
    start = re.search(rf"\bsubroutine\s+{re.escape(name)}\b", text, re.IGNORECASE)
    if not start:
        return None
    end = re.search(r"\bend\s+subroutine\b", text[start.end():], re.IGNORECASE)
    stop = start.end() + (end.start() if end else len(text))
    return text[start.start():stop]
