"""FastMCP server exposing HICAR knowledge as tools, resources and prompts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .bootstrap import load_knowledge
from .codesearch import lexical, symbols
from .codesearch.service import SemanticService
from .config import Config, discover
from .generate.nml_gen import generate_namelist, normalize_selections
from .kb import Knowledge
from .validate import binary as binmod
from .validate.static import validate_text


@dataclass
class State:
    config: Config
    kn: Knowledge
    semantic: SemanticService
    _symbols: list | None = None

    def symbol_index(self):
        if self._symbols is None and self.config.repo_root is not None:
            self._symbols = symbols.build_symbol_index(self.config.repo_root)
        return self._symbols or []

    def code_roots(self) -> list[Path]:
        if self.config.repo_root is not None:
            return [self.config.repo_root / "src", self.config.repo_root / "docs"]
        return [self.config.data_dir / "docs"]


def build_server(config: Config | None = None) -> FastMCP:
    config = config or discover()
    kn = load_knowledge(config)
    state = State(config=config, kn=kn, semantic=SemanticService(config))
    mcp = FastMCP("HICAR")

    # ---------------------------------------------------------------- namelist
    @mcp.tool()
    def list_namelist_groups() -> list[dict]:
        """List HICAR namelist groups (&blocks) with option counts."""
        out = []
        for g in state.kn.list_groups():
            block = state.kn.schema.group_blocks.get(g, g.lower())
            out.append({"group": g, "block": f"&{block}",
                        "n_options": len(state.kn.options_in_group(g))})
        return out

    @mcp.tool()
    def list_namelist_options(group: str | None = None) -> list[dict]:
        """List namelist options, optionally filtered to one group."""
        opts = state.kn.options_in_group(group) if group else list(state.kn.schema.options.values())
        return [{"name": o.name, "group": o.group, "type": o.inferred_type.value,
                 "default": o.default, "summary": o.description.splitlines()[0] if o.description else ""}
                for o in sorted(opts, key=lambda o: (o.group, o.name))]

    @mcp.tool()
    def get_namelist_option(name: str) -> dict:
        """Full metadata for one namelist option: group, &block, type, default,
        allowed values, range, units and description."""
        opt = state.kn.get_option(name)
        if opt is None:
            return {"error": f"unknown option '{name}'"}
        return opt.to_dict()

    @mcp.tool()
    def search_namelist_options(query: str, group: str | None = None) -> list[dict]:
        """Search namelist options by name/description (substring)."""
        return [{"name": o.name, "group": o.group, "type": o.inferred_type.value,
                 "summary": o.description.splitlines()[0] if o.description else ""}
                for o in state.kn.search_options(query, group)]

    @mcp.tool()
    def validate_namelist(content: str, use_binary: bool = False) -> dict:
        """Validate a namelist string. Static checks always run (unknown
        groups/options, bad enum values, out-of-range, type/per-nest issues).
        If use_binary and a compiled HICAR is available, also run --check-nml."""
        issues = [i.to_dict() for i in validate_text(content, state.kn)]
        result = {"ok": not any(i["severity"] == "error" for i in issues), "issues": issues}
        if use_binary:
            if state.config.binary is None:
                result["binary"] = {"available": False,
                                    "note": "No compiled HICAR found (set HICAR_BINARY or build it)."}
            else:
                r = binmod.check_namelist(state.config.binary, content)
                result["binary"] = {"available": True, "ok": r.ok, "returncode": r.returncode,
                                    "stdout": r.stdout[-4000:], "stderr": r.stderr[-2000:], "note": r.note}
        return result

    @mcp.tool()
    def generate_namelist_tool(
        mode: str = "full",
        mp: str | None = None, pbl: str | None = None, lsm: str | None = None,
        rad: str | None = None, conv: str | None = None, water: str | None = None,
        sm: str | None = None, sfc: str | None = None, wind: str | None = None,
        use_binary: bool = False,
    ) -> dict:
        """Generate a namelist ('full' or 'minimal') with optional physics
        scheme selections. With use_binary, delegate to HICAR --gen-nml instead."""
        if use_binary and state.config.binary is not None:
            r = binmod.generate_namelist(state.config.binary)
            return {"source": "binary", "ok": r.ok, "namelist": r.stdout, "note": r.note}
        raw = {"mp": mp, "pbl": pbl, "lsm": lsm, "rad": rad, "conv": conv,
               "water": water, "sm": sm, "sfc": sfc, "wind": wind}
        sel = normalize_selections(state.kn, {k: v for k, v in raw.items() if v})
        return {"source": "static", "mode": mode,
                "namelist": generate_namelist(state.kn, mode=mode, selections=sel)}

    @mcp.tool()
    def explain_namelist(content: str) -> dict:
        """Parse a namelist and annotate every option with its description,
        type, default and allowed values; flag any validation issues."""
        from .nml.reader import read_namelist
        parsed = read_namelist(content)
        annotated = []
        for g in parsed.groups:
            for a in g.assignments:
                opt = state.kn.get_option(a.key)
                annotated.append({
                    "group": g.name, "option": a.key, "value": a.value,
                    "known": opt is not None,
                    "type": opt.inferred_type.value if opt else None,
                    "default": opt.default if opt else None,
                    "description": opt.description if opt else None,
                })
        return {"options": annotated,
                "issues": [i.to_dict() for i in validate_text(content, state.kn)]}

    # ------------------------------------------------------------------ schemes
    @mcp.tool()
    def list_physics_categories() -> list[str]:
        """List physics-scheme categories (microphysics, pbl, radiation, ...)."""
        return state.kn.scheme_categories()

    @mcp.tool()
    def get_physics_schemes(category: str) -> list[dict]:
        """List selectable schemes for a category (or selector like 'mp'),
        with codes, originating constants, and supported status."""
        return [s.to_dict() for s in state.kn.schemes_for(category)]

    @mcp.tool()
    def resolve_physics_scheme(category: str, value: str) -> dict:
        """Resolve a scheme name or integer code within a category."""
        s = state.kn.resolve_scheme(category, value)
        return s.to_dict() if s else {"error": f"no scheme '{value}' in '{category}'"}

    # ---------------------------------------------------------------- variables
    @mcp.tool()
    def list_model_variables(filter: str | None = None) -> list[dict]:
        """List kVARS model/output variables (optionally substring-filtered)."""
        vars_ = state.kn.search_variables(filter) if filter else state.kn.variables
        return [{"kvar": v.kvar, "name": v.name, "units": v.units,
                 "long_name": v.long_name} for v in vars_]

    @mcp.tool()
    def get_model_variable(name: str) -> dict:
        """Full metadata for a model variable (by netCDF name or kVARS member)."""
        v = state.kn.get_variable(name)
        return v.to_dict() if v else {"error": f"unknown variable '{name}'"}

    @mcp.tool()
    def search_model_variables(query: str) -> list[dict]:
        """Search model variables by name/standard_name/description."""
        return [v.to_dict() for v in state.kn.search_variables(query)]

    # ----------------------------------------------------------------- examples
    @mcp.tool()
    def list_example_namelists() -> list[str]:
        """List bundled example namelists."""
        return state.kn.list_examples()

    @mcp.tool()
    def get_example_namelist(name: str) -> dict:
        """Return the contents of an example namelist."""
        c = state.kn.get_example(name)
        return {"name": name, "content": c} if c else {"error": f"no example '{name}'"}

    @mcp.tool()
    def search_example_namelists(query: str) -> list[dict]:
        """Search example namelists for a substring."""
        return state.kn.search_examples(query)

    # --------------------------------------------------------------------- docs
    @mcp.tool()
    def list_docs() -> list[dict]:
        """List HICAR documentation pages."""
        return [{"name": d.name, "title": d.title} for d in state.kn.list_docs()]

    @mcp.tool()
    def get_doc(name: str) -> dict:
        """Return a documentation page by file name or title."""
        d = state.kn.get_doc(name)
        return {"name": d.name, "title": d.title, "text": d.text} if d else {"error": f"no doc '{name}'"}

    @mcp.tool()
    def search_docs(query: str, max_results: int = 20) -> list[dict]:
        """Search the documentation (substring, with doc + line refs)."""
        return state.kn.search_docs(query, max_results)

    # --------------------------------------------------------------------- code
    @mcp.tool()
    def code_search(query: str, regex: bool = False, max_results: int = 100) -> dict:
        """Lexical search over HICAR source (.F90) and docs. Requires HICAR_REPO
        (live mode) for source; bundled mode searches docs only."""
        if state.config.repo_root is None:
            note = "Source search needs a HICAR checkout: set HICAR_REPO. Searching bundled docs only."
        else:
            note = ""
        hits = lexical.code_search(state.code_roots(), query, regex=regex, max_results=max_results)
        return {"note": note, "ripgrep": lexical.have_ripgrep(),
                "hits": [h.to_dict() for h in hits]}

    @mcp.tool()
    def find_symbol(name: str, kind: str | None = None) -> dict:
        """Find Fortran symbols (module/subroutine/function/type) by name.
        Requires HICAR_REPO (live mode)."""
        if state.config.repo_root is None:
            return {"error": "needs a HICAR checkout: set HICAR_REPO", "matches": []}
        found = symbols.find_symbol(state.symbol_index(), name, kind)
        return {"matches": [s.to_dict() for s in found[:50]]}

    @mcp.tool()
    def read_source(path: str | None = None, symbol: str | None = None,
                    start: int | None = None, end: int | None = None) -> dict:
        """Read HICAR source by file path (repo-rooted, line range) or by symbol
        name. Requires HICAR_REPO (live mode)."""
        if state.config.repo_root is None:
            return {"error": "needs a HICAR checkout: set HICAR_REPO"}
        if symbol:
            found = symbols.find_symbol(state.symbol_index(), symbol)
            if not found:
                return {"error": f"symbol '{symbol}' not found"}
            return symbols.read_symbol(state.config.repo_root, found[0])
        if path:
            return symbols.read_file(state.config.repo_root, path, start, end)
        return {"error": "provide either 'path' or 'symbol'"}

    @mcp.tool()
    def semantic_search(query: str, k: int = 10, kind: str = "all") -> dict:
        """Natural-language semantic search over HICAR code + docs. Falls back
        to lexical search if the embedding model isn't available."""
        res = state.semantic.search(query, k=k, kind=kind)
        if not res.get("available"):
            hits = lexical.code_search(state.code_roots(), query, max_results=k)
            res["lexical_fallback"] = [h.to_dict() for h in hits]
        return res

    # -------------------------------------------------------------- diagnostics
    @mcp.tool()
    def server_status() -> dict:
        """Report server mode, discovered paths, artifact/HICAR version, and
        which optional features (binary, ripgrep, semantic) are active."""
        return {
            "mode": state.config.mode,
            "repo_root": str(state.config.repo_root) if state.config.repo_root else None,
            "hicar_binary": str(state.config.binary) if state.config.binary else None,
            "hicar_version": state.kn.version.get("hicar_version"),
            "artifact_schema": state.kn.version.get("artifact_schema"),
            "counts": {
                "namelist_options": len(state.kn.schema.options),
                "schemes": len(state.kn.schemes),
                "variables": len(state.kn.variables),
                "docs": len(state.kn.docs),
                "examples": len(state.kn.examples),
            },
            "ripgrep": lexical.have_ripgrep(),
            "semantic_available": state.semantic.available(),
        }

    _register_resources(mcp, state)
    _register_prompts(mcp)
    return mcp


def _register_resources(mcp: FastMCP, state: State) -> None:
    @mcp.resource("hicar://namelist/schema")
    def schema_resource() -> str:
        from .artifacts.schema_v1 import dump_schema
        return json.dumps(dump_schema(state.kn.schema), indent=2)

    @mcp.resource("hicar://namelist/option/{name}")
    def option_resource(name: str) -> str:
        opt = state.kn.get_option(name)
        return json.dumps(opt.to_dict() if opt else {"error": "unknown"}, indent=2)

    @mcp.resource("hicar://schemes/{category}")
    def schemes_resource(category: str) -> str:
        return json.dumps([s.to_dict() for s in state.kn.schemes_for(category)], indent=2)

    @mcp.resource("hicar://variables")
    def variables_resource() -> str:
        return json.dumps([v.to_dict() for v in state.kn.variables], indent=2)

    @mcp.resource("hicar://variable/{name}")
    def variable_resource(name: str) -> str:
        v = state.kn.get_variable(name)
        return json.dumps(v.to_dict() if v else {"error": "unknown"}, indent=2)

    @mcp.resource("hicar://docs/{name}")
    def doc_resource(name: str) -> str:
        d = state.kn.get_doc(name)
        return d.text if d else f"# Unknown doc '{name}'"

    @mcp.resource("hicar://examples/{name}")
    def example_resource(name: str) -> str:
        c = state.kn.get_example(name)
        return c if c else f"! unknown example '{name}'"


def _register_prompts(mcp: FastMCP) -> None:
    @mcp.prompt()
    def configure_hicar_run(use_case: str) -> str:
        """Guided prompt to build a HICAR namelist for a described use case."""
        return (
            f"Help me configure a HICAR run for: {use_case}.\n"
            "1. Use list_physics_categories and get_physics_schemes to choose schemes.\n"
            "2. Call generate_namelist_tool(mode='minimal', ...) with those schemes.\n"
            "3. Fill REQUIRED fields (dates, file paths, domain) using get_namelist_option for each.\n"
            "4. Run validate_namelist on the result and fix any issues."
        )

    @mcp.prompt()
    def debug_namelist_error(error_text: str) -> str:
        """Guided prompt to diagnose a HICAR namelist/runtime error."""
        return (
            f"I hit this HICAR error:\n{error_text}\n\n"
            "Diagnose it: validate_namelist on my config, look up offending options with "
            "get_namelist_option, search docs (search_docs) and the errors guide, and use "
            "code_search/semantic_search to trace where the message originates."
        )

    @mcp.prompt()
    def explain_physics_choice(category: str) -> str:
        """Compare the available schemes in a physics category."""
        return (
            f"Compare HICAR's {category} schemes. Use get_physics_schemes('{category}') for the "
            "options, note which are supported, and summarize trade-offs, citing docs where relevant."
        )
