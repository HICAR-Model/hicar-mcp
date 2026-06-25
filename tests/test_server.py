"""End-to-end server tests via the FastMCP in-process API (bundled + live)."""

from __future__ import annotations

import json

from hicar_mcp.server import build_server


def _extract(r):
    if isinstance(r, tuple):
        content, structured = r[0], (r[1] if len(r) > 1 else None)
        if structured is not None:
            return structured
        r = content
    if isinstance(r, list) and r:
        text = getattr(r[0], "text", None)
        if text is not None:
            try:
                return json.loads(text)
            except ValueError:
                return text
    return r


async def _call(mcp, tool, **kw):
    return _extract(await mcp.call_tool(tool, kw))


async def test_server_registers_surface(bundled_config):
    mcp = build_server(bundled_config)
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert {"get_namelist_option", "get_physics_schemes", "validate_namelist",
            "semantic_search", "server_status"} <= names
    assert len(await mcp.list_prompts()) == 3
    assert len(await mcp.list_resource_templates()) >= 4


async def test_server_status_bundled(bundled_config):
    mcp = build_server(bundled_config)
    st = await _call(mcp, "server_status")
    assert st["mode"] == "bundled"
    assert st["counts"]["namelist_options"] >= 4


async def test_namelist_and_scheme_tools(bundled_config):
    mcp = build_server(bundled_config)
    mp = await _call(mcp, "get_namelist_option", name="mp")
    assert mp["group"] == "Physics"
    schemes = await _call(mcp, "get_physics_schemes", category="microphysics")
    schemes = schemes.get("result", schemes) if isinstance(schemes, dict) else schemes
    assert any(s["name"] == "morrison" and s["code"] == 3 for s in schemes)

    val = await _call(mcp, "validate_namelist", content="&physics\n mp='banana'\n/")
    assert val["ok"] is False
    gen = await _call(mcp, "generate_namelist_tool", mode="minimal", mp="morrison")
    assert "mp = 'morrison'" in gen["namelist"]


async def test_code_tools_require_repo_in_bundled(bundled_config):
    mcp = build_server(bundled_config)
    fs = await _call(mcp, "find_symbol", name="mp_step")
    assert "error" in fs
    rs = await _call(mcp, "read_source", symbol="mp_step")
    assert "error" in rs


async def test_code_tools_live(live_config):
    mcp = build_server(live_config)
    cs = await _call(mcp, "code_search", query="mp_step")
    assert any(h["path"].endswith("mp_driver.F90") for h in cs["hits"])
    fs = await _call(mcp, "find_symbol", name="mp_step")
    assert fs["matches"] and fs["matches"][0]["kind"] == "subroutine"
    rs = await _call(mcp, "read_source", symbol="mp_step")
    assert "mp_step" in rs["text"]


async def test_semantic_fallback_when_no_index(bundled_config):
    # bundled fixture has no prebuilt index -> semantic unavailable -> lexical fallback
    mcp = build_server(bundled_config)
    res = await _call(mcp, "semantic_search", query="microphysics")
    assert res["available"] is False
    assert "lexical_fallback" in res


async def test_semantic_live_builds_index(live_config):
    mcp = build_server(live_config)
    res = await _call(mcp, "semantic_search", query="microphysics scheme")
    assert res["available"] is True
    assert res["results"]
    assert res["backend"].startswith("fake")
