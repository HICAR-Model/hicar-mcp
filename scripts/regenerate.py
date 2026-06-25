#!/usr/bin/env python3
"""CI/maintainer entry point to regenerate bundled artifacts from HICAR source.

Usage:
    python scripts/regenerate.py --repo /path/to/HICAR [--commit SHA] [--built-at ISO] [--no-embed]

Equivalent to `hicar-mcp regenerate`, but runnable straight from a checkout
(adds ``src`` to sys.path) so CI need not pip-install first.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from hicar_mcp.regenerate import regenerate  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Regenerate hicar-mcp bundled artifacts")
    ap.add_argument("--repo", required=True, help="path to a HICAR checkout")
    ap.add_argument("--out", help="output data dir (default: bundled package data dir)")
    ap.add_argument("--commit", help="HICAR commit sha to record")
    ap.add_argument("--built-at", dest="built_at", help="build timestamp (ISO) to record")
    ap.add_argument("--embedder", help="embedder spec (default: local bge model)")
    ap.add_argument("--no-embed", action="store_true", help="skip the semantic index")
    args = ap.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    if not (repo / "src/utilities/namelist_utilities.F90").exists():
        print(f"error: {repo} is not a HICAR checkout", file=sys.stderr)
        return 1
    out = Path(args.out).expanduser().resolve() if args.out else None
    summary = regenerate(
        repo, out_dir=out, commit=args.commit, built_at=args.built_at,
        build_embeddings=not args.no_embed, embedder_spec=args.embedder,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
