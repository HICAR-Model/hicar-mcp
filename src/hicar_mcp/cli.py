"""Command-line entry point: serve | doctor | index | regenerate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _cmd_serve(args) -> int:
    try:
        from .server import build_server
    except ImportError as e:
        print(f"error: the MCP SDK is required to serve ({e}). Install with `pip install mcp`.",
              file=sys.stderr)
        return 1
    build_server().run()
    return 0


def _cmd_doctor(args) -> int:
    from .bootstrap import load_knowledge
    from .codesearch.lexical import have_ripgrep
    from .codesearch.service import SemanticService
    from .config import discover

    config = discover()
    print(f"hicar-mcp doctor")
    print(f"  mode:          {config.mode}")
    print(f"  repo_root:     {config.repo_root or '(none; bundled mode)'}")
    print(f"  data_dir:      {config.data_dir}")
    print(f"  hicar_binary:  {config.binary or '(none)'}")
    print(f"  cache_dir:     {config.cache_dir}")
    print(f"  ripgrep:       {'yes' if have_ripgrep() else 'no (pure-Python fallback)'}")
    try:
        kn = load_knowledge(config)
        print(f"  knowledge:     {len(kn.schema.options)} options, {len(kn.schemes)} schemes, "
              f"{len(kn.variables)} variables, {len(kn.docs)} docs "
              f"(HICAR {kn.version.get('hicar_version')})")
    except Exception as e:  # noqa: BLE001
        print(f"  knowledge:     ERROR: {e}")
        print("                 -> set HICAR_REPO or run `hicar-mcp regenerate`.")
        return 1
    sem = SemanticService(config)
    print(f"  semantic:      {'available' if sem.available() else 'unavailable'}"
          f" {'' if sem.available() else '(install hicar-mcp[semantic])'}")
    return 0


def _cmd_index(args) -> int:
    from .codesearch.semantic import SemanticIndex, chunk_repo, corpus_hash
    from .config import discover
    from .embed.base import make_embedder

    config = discover()
    if config.repo_root is None:
        print("error: `index` builds a live index and needs HICAR_REPO set.", file=sys.stderr)
        return 1
    emb = make_embedder(config.embedder_override)
    if emb is None:
        print("error: no embedder available; install hicar-mcp[semantic].", file=sys.stderr)
        return 1
    chunks = chunk_repo(config.repo_root)
    idx = SemanticIndex.build(chunks, emb, corpus_hash_=corpus_hash(config.repo_root))
    out = config.cache_dir / "index"
    idx.save(out)
    print(f"built index: {len(chunks)} chunks with {emb.name} -> {out}")
    return 0


def _cmd_regenerate(args) -> int:
    from .regenerate import regenerate
    repo = Path(args.repo).expanduser().resolve()
    if not (repo / "src/utilities/namelist_utilities.F90").exists():
        print(f"error: {repo} does not look like a HICAR checkout.", file=sys.stderr)
        return 1
    out = Path(args.out).expanduser().resolve() if args.out else None
    summary = regenerate(
        repo, out_dir=out, commit=args.commit, built_at=args.built_at,
        build_embeddings=not args.no_embed, embedder_spec=args.embedder,
    )
    print(json.dumps(summary, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hicar-mcp", description="HICAR MCP server")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("serve", help="run the MCP server over stdio (default)")
    sub.add_parser("doctor", help="report discovered config and feature availability")
    sub.add_parser("index", help="build the live semantic index (needs HICAR_REPO)")

    rg = sub.add_parser("regenerate", help="regenerate bundled artifacts from a HICAR checkout")
    rg.add_argument("--repo", required=True, help="path to a HICAR checkout")
    rg.add_argument("--out", help="output data dir (default: bundled package data dir)")
    rg.add_argument("--commit", help="HICAR commit sha to record")
    rg.add_argument("--built-at", help="build timestamp to record")
    rg.add_argument("--embedder", help="embedder spec (default: local bge model)")
    rg.add_argument("--no-embed", action="store_true", help="skip building the semantic index")

    args = parser.parse_args(argv)
    command = args.command or "serve"
    return {
        "serve": _cmd_serve,
        "doctor": _cmd_doctor,
        "index": _cmd_index,
        "regenerate": _cmd_regenerate,
    }[command](args)


if __name__ == "__main__":
    raise SystemExit(main())
