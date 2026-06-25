"""Parser + schema + scheme + variable extraction tests."""

from __future__ import annotations

from hicar_mcp.knowledge import constants, namelist_source, namelist_schema, schemes, varcatalog
from hicar_mcp.models import NmlType


def test_parse_constants(constants_text):
    k = constants.parse_k_constants(constants_text)
    assert k["kMP_MORRISON"] == 3
    assert k["kMAX_NESTS"] == 10
    kvars = constants.parse_kvars(constants_text)
    assert kvars[:3] == ["u", "v", "w"]
    assert "last_var" not in kvars
    assert "pressure" in kvars


def test_parse_metadata_basic(nml_util_text):
    raw = namelist_source.parse_metadata(nml_util_text)
    assert set(["debug", "nests", "start_date", "mp", "outputinterval"]) <= set(raw)
    assert raw["debug"].default == ".False."
    assert raw["nests"].max_token == "kMAX_NESTS"
    assert raw["nests"].min_token == "1"


def test_parse_metadata_multiline_description(nml_util_text):
    raw = namelist_source.parse_metadata(nml_util_text)
    desc = raw["mp"].description
    assert desc.startswith("Microphysics scheme to use:")
    assert "'Morrison' = Morrison" in desc
    assert "NOT SUPPORTED" in desc
    # newline-joined, not a single run-on line
    assert "\n" in desc


def test_group_blocks_and_namelist_blocks(nml_util_text, fixtures_repo):
    gblocks = namelist_source.parse_group_blocks(nml_util_text)
    assert gblocks["General"] == "general"
    assert gblocks["Physics"] == "physics"
    options_txt = (fixtures_repo / "src/objects/options_obj.F90").read_text()
    nblocks = namelist_source.parse_namelist_blocks(options_txt)
    assert nblocks["general"] == ["debug", "nests", "start_date"]
    assert nblocks["physics"] == ["mp", "pbl", "lsm"]


def test_build_schema_enum_and_types(nml_util_text, constants_text):
    raw = namelist_source.parse_metadata(nml_util_text)
    k = constants.parse_k_constants(constants_text)
    gblocks = namelist_source.parse_group_blocks(nml_util_text)
    schema = namelist_schema.build_schema(raw, gblocks, {}, k)

    mp = schema.get("mp")
    assert mp.inferred_type == NmlType.STRING_ENUM
    pairs = {(e.name, e.code) for e in mp.enum_values}
    assert ("morrison", 3) in pairs and ("thompson", 1) in pairs
    morrison = next(e for e in mp.enum_values if e.name == "morrison")
    assert morrison.constant == "kMP_MORRISON"

    assert schema.get("debug").inferred_type == NmlType.BOOL
    assert schema.get("nests").inferred_type == NmlType.INT
    assert schema.get("start_date").inferred_type == NmlType.DATE


def test_min_max_activation(nml_live_schema):
    schema = nml_live_schema
    nests = schema.get("nests")
    assert nests.minimum == 1.0 and nests.maximum == 10.0
    # outputinterval has only a min set; max must NOT default to 0
    oi = schema.get("outputinterval")
    assert oi.minimum == 1.0
    assert oi.maximum is None
    # debug has no range
    assert schema.get("debug").minimum is None and schema.get("debug").maximum is None


def test_scheme_registry(nml_live_schema):
    reg = schemes.build_scheme_registry(nml_live_schema.options)
    mp = [s for s in reg if s.selector == "mp"]
    by_name = {s.name: s for s in mp}
    assert by_name["morrison"].code == 3 and by_name["morrison"].supported
    assert not by_name["wsm6"].supported          # marked (NOT SUPPORTED)
    assert "none" not in by_name                   # sentinel dropped


def test_varcatalog(fixtures_repo):
    text = (fixtures_repo / "src/io/default_output_metadata.F90").read_text()
    vs = varcatalog.parse_varcatalog(text)
    by_name = {v.name: v for v in vs}
    assert by_name["u"].standard_name == "eastward_wind"
    assert by_name["u"].units == "m s-1"
    assert by_name["u"].has_forcing_hook and by_name["u"].forcing_option == "uvar"
    assert by_name["pressure"].maxval == 110000.0


# --- helper fixture local to this module ---
import pytest  # noqa: E402


@pytest.fixture()
def nml_live_schema(nml_util_text, constants_text):
    raw = namelist_source.parse_metadata(nml_util_text)
    k = constants.parse_k_constants(constants_text)
    gblocks = namelist_source.parse_group_blocks(nml_util_text)
    return namelist_schema.build_schema(raw, gblocks, {}, k)
