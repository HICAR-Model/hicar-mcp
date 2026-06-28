# hicar-mcp

A **Model Context Protocol (MCP) server** that gives AI assistants structured,
authoritative knowledge of the [HICAR atmospheric model](https://github.com/HICAR-Model/HICAR):
every namelist option, the physics-scheme registry, the ~375-variable output
catalog, the documentation, and the source code.

Point any MCP client (Claude Desktop, Claude Code, Cursor, …) at it and ask
things like *"what does the `mp` option do and what are its valid values?"*,
*"which microphysics schemes are supported?"*, *"what units is `pressure_i`
in?"*, *"generate a minimal namelist using Morrison microphysics"*, or
*"where is the wind solver iterated?"*.

## Install

```bash
pipx install "hicar-mcp[semantic]"      # recommended (isolated, with semantic search)
# or
uv tool install "hicar-mcp[semantic]"
# or, lightweight (no semantic search):
pip install hicar-mcp
```

The server ships with **pre-extracted knowledge bundled in**, so it works with
**zero configuration** — you do *not* need a HICAR checkout or a compiled
binary. Optional upgrades light up automatically (see *Modes* below).

## Configure your MCP client

**Claude Desktop / Cursor** — add to the `mcpServers` block of the client config:

```json
{
  "mcpServers": {
    "hicar": { "command": "hicar-mcp", "args": ["serve"] }
  }
}
```

**Claude Code:**

```bash
claude mcp add hicar -- hicar-mcp serve
```

To enable source-aware tools (`code_search`, `find_symbol`, `read_source`) and
always-fresh metadata, point it at a HICAR checkout:

```json
{ "mcpServers": { "hicar": {
    "command": "hicar-mcp", "args": ["serve"],
    "env": { "HICAR_REPO": "/abs/path/to/HICAR" } } } }
```

## Modes & graceful degradation

| Feature | Needs | Without it |
|---|---|---|
| Namelist / scheme / variable / docs lookup, static validation & generation | nothing (bundled) | — |
| `code_search`, `find_symbol`, `read_source`, live-fresh metadata | `HICAR_REPO` set (live mode) | source tools report how to enable |
| `validate_namelist(use_binary=True)`, `--gen-nml` parity | a compiled `HICAR` (`HICAR_BINARY` or `bin/HICAR`) | static validation only |
| `semantic_search` | `hicar-mcp[semantic]` (local model, offline after first download) | falls back to lexical search |
| Higher-quality semantic (live rebuild) | `hicar-mcp[api]` + `VOYAGE_API_KEY`/`OPENAI_API_KEY` | local model |

Run `hicar-mcp doctor` to see exactly what was discovered and what is degraded.

## Tools

Namelist: `list_namelist_groups`, `list_namelist_options`, `get_namelist_option`,
`search_namelist_options`, `validate_namelist`, `generate_namelist_tool`,
`explain_namelist`. Schemes: `list_physics_categories`, `get_physics_schemes`,
`resolve_physics_scheme`. Variables: `list_model_variables`, `get_model_variable`,
`search_model_variables`. Examples: `list_example_namelists`, `get_example_namelist`,
`search_example_namelists`. Docs: `list_docs`, `get_doc`, `search_docs`. Code:
`code_search`, `find_symbol`, `read_source`, `semantic_search`. Diagnostics:
`server_status`.

Resources (`hicar://…`) and guided prompts (`configure_hicar_run`,
`debug_namelist_error`, `explain_physics_choice`) are also provided.

## How the knowledge stays current

The bundled artifacts are regenerated from HICAR source by CI on each HICAR
release (a workflow in the HICAR repo dispatches to this one). To regenerate
locally:

```bash
hicar-mcp regenerate --repo /path/to/HICAR
```

## MCP Registry

Published to the official MCP Registry as `io.github.HICAR-Model/hicar-mcp`.
The line below lets the registry verify that this PyPI package and the registry
entry have the same owner; do not remove it.

<!-- mcp-name: io.github.HICAR-Model/hicar-mcp -->
