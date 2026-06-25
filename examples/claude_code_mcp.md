# Using hicar-mcp with Claude Code

Install (isolated, with semantic search):

```bash
pipx install "hicar-mcp[semantic]"
```

Add the server (bundled mode, zero config):

```bash
claude mcp add hicar -- hicar-mcp serve
```

Live mode (source-aware tools + always-fresh metadata) — point it at a checkout:

```bash
claude mcp add hicar -e HICAR_REPO=/abs/path/to/HICAR -- hicar-mcp serve
```

Verify discovery and feature availability at any time:

```bash
hicar-mcp doctor
```

Then ask Claude things like:

- "Explain the `mp` namelist option and list its valid values."
- "Which microphysics schemes does HICAR support?"
- "Generate a minimal namelist using Morrison microphysics and the YSU PBL."
- "Validate this namelist:" (paste it)
- "Where is the iterative wind solver implemented?" (live mode)
