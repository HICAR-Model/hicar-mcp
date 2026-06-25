"""Optional validation/generation backed by a compiled HICAR binary.

These are best-effort: the binary's ``-v``/``--check-nml``/``--gen-nml`` paths
run a single image and ``stop`` before the MPI loop, so a direct invocation
usually works. We always run with a timeout, capture output, and only write to
server-controlled temp files.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

_TIMEOUT = 60


@dataclass
class BinaryResult:
    ok: bool
    returncode: int | None
    stdout: str
    stderr: str
    note: str = ""


def _run(binary: Path, args: list[str]) -> BinaryResult:
    try:
        proc = subprocess.run(
            [str(binary), *args],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
            cwd=binary.parent,
        )
        return BinaryResult(
            ok=proc.returncode == 0,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )
    except subprocess.TimeoutExpired:
        return BinaryResult(False, None, "", "", note="HICAR binary timed out")
    except OSError as e:
        return BinaryResult(False, None, "", "", note=f"could not run HICAR binary: {e}")


def check_namelist(binary: Path, content: str) -> BinaryResult:
    with tempfile.NamedTemporaryFile("w", suffix=".nml", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        return _run(binary, ["--check-nml", path])
    finally:
        Path(path).unlink(missing_ok=True)


def generate_namelist(binary: Path) -> BinaryResult:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "generated.nml"
        res = _run(binary, ["--gen-nml", str(out)])
        if out.exists():
            res.stdout = out.read_text(encoding="utf-8", errors="replace")
            res.ok = True
        return res
