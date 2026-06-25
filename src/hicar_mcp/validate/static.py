"""Static namelist validation against the parsed schema (no binary required)."""

from __future__ import annotations

import difflib

from ..kb import Knowledge
from ..models import Issue, NmlType
from ..nml.reader import (
    ParsedNml,
    as_number,
    is_bool,
    read_namelist,
    split_array,
    unquote,
)


def _enum_ok(value: str, opt) -> bool:
    v = unquote(value).strip().lower()
    for ev in opt.enum_values:
        if ev.name and ev.name.lower() == v:
            return True
        if ev.code is not None and str(ev.code) == v:
            return True
    return False


def _allowed_str(opt) -> str:
    parts = []
    for ev in opt.enum_values:
        if ev.name and ev.code is not None:
            parts.append(f"{ev.name} ({ev.code})")
        elif ev.name:
            parts.append(ev.name)
        elif ev.code is not None:
            parts.append(str(ev.code))
    return ", ".join(parts)


def validate_parsed(parsed: ParsedNml, kn: Knowledge) -> list[Issue]:
    issues: list[Issue] = []
    schema = kn.schema
    known_blocks = set(schema.block_vars) | set(schema.group_blocks.values())
    all_option_names = list(schema.options)

    for pi in parsed.issues:
        issues.append(Issue("warning", "", "", f"parse: {pi}"))

    # determine nests for per-nest checks
    nests = 1
    g_general = parsed.get_group("general")
    if g_general:
        a = g_general.get("nests")
        if a and as_number(a.value) is not None:
            nests = int(as_number(a.value))

    for group in parsed.groups:
        if group.name not in known_blocks:
            sugg = difflib.get_close_matches(group.name, known_blocks, n=1)
            issues.append(
                Issue(
                    "error",
                    group.name,
                    "",
                    f"Unknown namelist group &{group.name}.",
                    f"Did you mean &{sugg[0]}?" if sugg else "",
                )
            )
            continue

        for a in group.assignments:
            opt = schema.get(a.key)
            if opt is None:
                sugg = difflib.get_close_matches(a.key, all_option_names, n=1)
                issues.append(
                    Issue(
                        "error",
                        group.name,
                        a.key,
                        f"Unknown option '{a.key}' (line {a.line}).",
                        f"Did you mean '{sugg[0]}'?" if sugg else "",
                    )
                )
                continue

            expected = schema.block_for(a.key)
            if expected and expected != group.name:
                issues.append(
                    Issue(
                        "warning",
                        group.name,
                        a.key,
                        f"'{a.key}' belongs in &{expected}, not &{group.name} (line {a.line}).",
                        f"Move it to the &{expected} group.",
                    )
                )

            _check_value(issues, group.name, a, opt, nests)

    return issues


def _check_value(issues, block, a, opt, nests) -> None:
    # A value equal to HICAR's own default is always accepted, even when that
    # default is a sentinel outside the documented range (e.g. tend_*=-1.0).
    if a.value and unquote(a.value).strip() == (opt.default or "").strip():
        return
    items = split_array(a.value) if a.value else []
    first = items[0] if items else a.value

    # enum membership
    if opt.enum_values:
        for it in (items or [a.value]):
            if not _enum_ok(it, opt):
                issues.append(
                    Issue(
                        "error",
                        block,
                        a.key,
                        f"'{unquote(it)}' is not a valid value for '{a.key}' (line {a.line}).",
                        f"Allowed: {_allowed_str(opt)}.",
                    )
                )
        return

    # range
    if opt.minimum is not None or opt.maximum is not None:
        for it in (items or [a.value]):
            num = as_number(it)
            if num is None:
                continue
            if opt.minimum is not None and num < opt.minimum:
                issues.append(
                    Issue("error", block, a.key,
                          f"{a.key}={num} is below the minimum {opt.minimum} (line {a.line}).")
                )
            if opt.maximum is not None and num > opt.maximum:
                issues.append(
                    Issue("error", block, a.key,
                          f"{a.key}={num} exceeds the maximum {opt.maximum} (line {a.line}).")
                )

    # conservative type checks
    if opt.inferred_type == NmlType.BOOL and a.value and not is_bool(a.value):
        issues.append(
            Issue("warning", block, a.key,
                  f"'{a.key}' expects a logical (.true./.false.) but got {a.value!r} (line {a.line}).")
        )
    elif opt.inferred_type == NmlType.INT and a.value and as_number(first) is not None:
        if not float(as_number(first)).is_integer():
            issues.append(
                Issue("warning", block, a.key,
                      f"'{a.key}' expects an integer but got {a.value!r} (line {a.line}).")
            )

    # per-nest arity
    if opt.nest_semantics == 2 and nests > 1 and items and len(items) < nests:
        issues.append(
            Issue("warning", block, a.key,
                  f"'{a.key}' should be set per nest ({nests} values expected, got {len(items)}) (line {a.line}).")
        )


def validate_text(text: str, kn: Knowledge) -> list[Issue]:
    return validate_parsed(read_namelist(text), kn)
