# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Chethan Dandebala Venkatarama
"""``ek lean-links``: every P claim's theorem must exist in the built Lean project.

For ``proof: proofs/RhythmUnits/Basic.lean#RhythmUnits.period_pos`` this imports the module
``RhythmUnits.Basic`` (the path relative to the Lake folder) and runs ``#check @RhythmUnits.period_pos``,
using one temporary file and one ``lake env lean`` call for all claims. Build the project first.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path, PurePath

from evidence_kernel.claims import Fatal, Report, load_ledger

# file:line:col: error: message (lean), or error: file:line:col: message (lake)
_DIAGNOSTIC = re.compile(r"^(error: )?[^:\n]*:(\d+):\d+: (error: )?(.*)$", re.MULTILINE)
_UNKNOWN = re.compile(r"unknown (identifier|constant)")


def add_parser(commands: argparse._SubParsersAction) -> None:
    p = commands.add_parser(
        "lean-links",
        help="check that every P claim's theorem exists in Lean",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("claims", type=Path, help="the claims.yaml file")
    p.add_argument("--lake-dir", type=Path, metavar="DIR", help="the Lake project folder (default: proofs/)")
    p.set_defaults(run=run)


def lean_module(path: str | PurePath) -> str:
    """The Lean module for a file path relative to the Lake folder: ``A/B.lean`` -> ``A.B``."""
    return ".".join(PurePath(path).with_suffix("").parts)


def run(args: argparse.Namespace) -> int:
    ledger = load_ledger(args.claims)
    lake_dir = (args.lake_dir or ledger.root / "proofs").resolve()
    report = Report()
    modules: dict[str, list[str]] = defaultdict(list)  # module -> claim ids
    names: dict[str, list[str]] = defaultdict(list)  # theorem -> claim ids
    for claim in ledger.claims:
        if claim["level"] != "P":
            continue
        file, name = claim["proof"].split("#", 1)
        try:
            module = lean_module((ledger.root / file).resolve().relative_to(lake_dir))
        except ValueError:
            report.error(f"{claim['id']}: {file} is not inside the Lake project {lake_dir}")
            continue
        modules[module].append(claim["id"])
        names[name].append(claim["id"])
    if not names:
        return report.finish(f"{args.claims}: no P claims to check")

    lines, owners = [], {}  # owners: line number -> (what the line refers to, claim ids)
    for module in sorted(modules):
        lines.append(f"import {module}")
        owners[len(lines)] = (f"module {module}", modules[module])
    lines.append("")
    for name, claim_ids in names.items():
        lines.append(f"#check @{name}")
        owners[len(lines)] = (name, claim_ids)

    code, output = _lake_env_lean(lake_dir, "\n".join(lines) + "\n")
    errors = 0
    for m in _DIAGNOSTIC.finditer(output):
        if not (m[1] or m[3]):
            continue  # warnings and #check output
        errors += 1
        what, claim_ids = owners.get(int(m[2]), ("", []))
        for claim_id in claim_ids:
            report.error(f"{claim_id}: Lean does not know {what}" if _UNKNOWN.search(m[4]) else f"{claim_id}: {m[4]}")
        if not claim_ids:
            report.error(f"Lean: {m[4]}")
    if code != 0 and not errors:
        report.error(f"lake env lean exited with status {code}:\n{output.strip()[-2000:]}")
    return report.finish(f"{args.claims}: all {len(names)} theorems found in {len(modules)} modules")


def _lake_env_lean(lake_dir: Path, source: str) -> tuple[int, str]:
    """Run ``lake env lean`` on ``source`` in a temporary file inside ``lake_dir``; always delete the file."""
    if not lake_dir.is_dir():
        raise Fatal(f"the Lake project folder {lake_dir} does not exist")
    fd, temp = tempfile.mkstemp(prefix="EkLeanLinks", suffix=".lean", dir=lake_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(source)
        command = ["lake", "env", "lean", Path(temp).name]
        try:
            done = subprocess.run(command, cwd=lake_dir, capture_output=True, encoding="utf-8", errors="replace")
        except FileNotFoundError:
            raise Fatal("lake is not on PATH: install Lean with elan, then build the project") from None
    finally:
        Path(temp).unlink(missing_ok=True)
    return done.returncode, f"{done.stdout or ''}\n{done.stderr or ''}"
