"""A tolerant Fortran-namelist reader.

Unlike a strict parser, malformed input produces *issues* (collected on the
result) rather than exceptions, so the validator can report problems instead
of crashing. Handles ``&group``/``/`` delimiters, ``!`` comments, multi-line
values, indexed array assignments and case-insensitive keys.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..knowledge.fortran import split_top_level, strip_inline_comment

_GROUP_START = re.compile(r"^[&$](\w+)(.*)$")
_ASSIGN_START = re.compile(r"(\b[A-Za-z]\w*)\s*(\([^)]*\))?\s*=")


@dataclass
class Assignment:
    key: str
    value: str
    line: int
    index: str | None = None


@dataclass
class Group:
    name: str          # lowercased block name
    line: int
    assignments: list[Assignment] = field(default_factory=list)

    def get(self, key: str) -> Assignment | None:
        for a in self.assignments:
            if a.key.lower() == key.lower():
                return a
        return None


@dataclass
class ParsedNml:
    groups: list[Group] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    def get_group(self, name: str) -> Group | None:
        for g in self.groups:
            if g.name == name.lower():
                return g
        return None


def _split_close(s: str) -> tuple[str, bool]:
    """Return (text-before-terminating-slash, closed?) honoring quotes."""
    in_s = in_d = False
    for i, c in enumerate(s):
        if c == "'" and not in_d:
            in_s = not in_s
        elif c == '"' and not in_s:
            in_d = not in_d
        elif c == "/" and not in_s and not in_d:
            return s[:i], True
    return s, False


def _parse_body(name: str, line: int, body: list[tuple[int, str]], issues: list[str]) -> Group:
    group = Group(name=name, line=line)
    pending: Assignment | None = None
    for lineno, text in body:
        matches = list(_ASSIGN_START.finditer(text))
        if not matches:
            if pending is not None:
                pending.value = (pending.value + " " + text).strip()
            else:
                issues.append(f"line {lineno}: unexpected text in &{name}: {text!r}")
            continue
        if matches[0].start() > 0 and pending is not None:
            pending.value = (pending.value + " " + text[: matches[0].start()]).strip()
        for j, mm in enumerate(matches):
            vstart = mm.end()
            vend = matches[j + 1].start() if j + 1 < len(matches) else len(text)
            value = text[vstart:vend].strip().strip(",").strip()
            pending = Assignment(
                key=mm.group(1), value=value, line=lineno, index=mm.group(2)
            )
            group.assignments.append(pending)
    return group


def read_namelist(text: str) -> ParsedNml:
    issues: list[str] = []
    groups: list[Group] = []
    cur_name: str | None = None
    cur_line = 0
    body: list[tuple[int, str]] = []

    for lineno, raw in enumerate(text.splitlines(), 1):
        s = strip_inline_comment(raw).strip()
        if not s:
            continue
        if cur_name is None:
            m = _GROUP_START.match(s)
            if m:
                cur_name = m.group(1).lower()
                cur_line = lineno
                body = []
                tail = m.group(2).strip()
                if tail:
                    before, closed = _split_close(tail)
                    if before.strip():
                        body.append((lineno, before.strip()))
                    if closed:
                        groups.append(_parse_body(cur_name, cur_line, body, issues))
                        cur_name = None
            # text outside any group is ignored silently (comments/blank already gone)
            continue

        # inside a group
        if s.lower() in ("&end", "$end", "/"):
            groups.append(_parse_body(cur_name, cur_line, body, issues))
            cur_name = None
            continue
        m = _GROUP_START.match(s)
        if m and m.group(1).lower() != "end":
            issues.append(f"line {lineno}: &{m.group(1)} started before &{cur_name} closed with '/'")
            groups.append(_parse_body(cur_name, cur_line, body, issues))
            cur_name = m.group(1).lower()
            cur_line = lineno
            body = []
            continue
        before, closed = _split_close(s)
        if before.strip():
            body.append((lineno, before.strip()))
        if closed:
            groups.append(_parse_body(cur_name, cur_line, body, issues))
            cur_name = None

    if cur_name is not None:
        issues.append(f"&{cur_name} (line {cur_line}) was not closed with '/'")
        groups.append(_parse_body(cur_name, cur_line, body, issues))

    return ParsedNml(groups=groups, issues=issues)


# ---- value interpretation helpers (used by the validator) ----

def unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] in "'\"" and v[-1] == v[0]:
        return v[1:-1]
    return v


def is_bool(v: str) -> bool:
    return unquote(v).strip().lower() in (".true.", ".false.", "t", "f", ".t.", ".f.", "true", "false")


def as_number(v: str):
    t = unquote(v).strip()
    try:
        return int(t)
    except ValueError:
        try:
            return float(t)
        except ValueError:
            return None


def split_array(v: str) -> list[str]:
    """Split a namelist value into items (comma- or space-separated).

    Quote-aware: a quoted scalar such as ``'variational solver'`` is never
    split on its internal whitespace.
    """
    parts = [p.strip() for p in split_top_level(v) if p.strip()]
    if len(parts) <= 1:
        single = v.strip()
        quoted = len(single) >= 2 and single[0] in "'\"" and single[-1] == single[0]
        if not quoted:
            ws = [p for p in re.split(r"\s+", single) if p]
            if len(ws) > 1:
                return ws
    return parts
