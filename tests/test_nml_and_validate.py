"""Namelist reader, static validation and generation tests."""

from __future__ import annotations

from hicar_mcp.generate.nml_gen import generate_namelist, normalize_selections
from hicar_mcp.nml.reader import read_namelist, split_array, unquote
from hicar_mcp.validate.static import validate_text


def test_reader_basics():
    text = """
! a comment
&general
  debug = .True.   ! inline comment
  nests = 2
  start_date = "2020-01-01 00:00:00"
/
&physics
  mp = 'morrison'
/
"""
    p = read_namelist(text)
    assert [g.name for g in p.groups] == ["general", "physics"]
    g = p.get_group("general")
    assert g.get("debug").value == ".True."
    assert g.get("nests").value == "2"
    assert unquote(g.get("start_date").value) == "2020-01-01 00:00:00"
    assert not p.issues


def test_reader_array_and_quoted_space():
    p = read_namelist("&wind\n wind = 'variational solver'\n parent_nest = 0, 1, 1\n/")
    g = p.get_group("wind")
    assert unquote(g.get("wind").value) == "variational solver"
    assert split_array(g.get("parent_nest").value) == ["0", "1", "1"]
    # a quoted multi-word value is a single item
    assert split_array(g.get("wind").value) == ["'variational solver'"]


def test_reader_unclosed_group_reports_issue():
    p = read_namelist("&general\n debug = .True.\n")
    assert any("not closed" in i for i in p.issues)


def test_validate_clean_example(kn_live):
    content = kn_live.get_example("sample.nml")
    issues = validate_text(content, kn_live)
    assert [i for i in issues if i.severity == "error"] == []


def test_validate_bad_enum_string_and_int(kn_live):
    errs = [i for i in validate_text("&physics\n mp='banana'\n/", kn_live) if i.severity == "error"]
    assert errs and "not a valid value" in errs[0].message
    # integer form of a valid code is accepted
    assert not [i for i in validate_text("&physics\n mp=3\n/", kn_live) if i.severity == "error"]
    # invalid integer code rejected
    assert [i for i in validate_text("&physics\n mp=99\n/", kn_live) if i.severity == "error"]


def test_validate_range_and_unknown(kn_live):
    errs = [i for i in validate_text("&general\n nests=99\n/", kn_live) if i.severity == "error"]
    assert any("maximum" in i.message for i in errs)
    unknown = [i for i in validate_text("&general\n notarealoption=1\n/", kn_live) if i.severity == "error"]
    assert unknown and "Unknown option" in unknown[0].message


def test_validate_wrong_group_warning(kn_live):
    # mp belongs in &physics; placing it in &general should warn
    warns = [i for i in validate_text("&general\n mp='morrison'\n/", kn_live) if i.severity == "warning"]
    assert any("belongs in &physics" in i.message for i in warns)


def test_validate_default_value_always_ok(kn_live):
    # outputinterval default 3600 with min 1 -> fine; sentinel defaults never flagged
    assert not [i for i in validate_text("&output\n outputinterval=3600\n/", kn_live)
                if i.severity == "error"]


def test_generate_minimal_includes_selected_scheme(kn_live):
    sel = normalize_selections(kn_live, {"mp": "morrison"})
    out = generate_namelist(kn_live, mode="minimal", selections=sel)
    assert "&physics" in out
    assert "mp = 'morrison'" in out
    # generated output must itself validate cleanly
    assert not [i for i in validate_text(out, kn_live) if i.severity == "error"]


def test_normalize_selections_resolves_code(kn_live):
    # passing the integer code resolves to the canonical name
    sel = normalize_selections(kn_live, {"mp": "3"})
    assert sel["mp"] == "morrison"
