# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Chethan Dandebala Venkatarama
"""``ek vectors``: check golden-vector files against golden-vectors@1 and the ledger's claim ids."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evidence_kernel.claims import VECTORS_SCHEMA, Fatal, Report, load_ledger, schema_errors


def add_parser(commands: argparse._SubParsersAction) -> None:
    p = commands.add_parser("vectors", help="check golden-vector files and the claims they cite", description=__doc__)
    p.add_argument("claims", type=Path, help="the claims.yaml file")
    p.add_argument("vectors_dir", type=Path, metavar="VECTORS_DIR", help="folder of *.json vector files")
    p.set_defaults(run=run)


def run(args: argparse.Namespace) -> int:
    ledger = load_ledger(args.claims)
    files = sorted(args.vectors_dir.glob("*.json"))  # the same files the runners read
    if not files:
        raise Fatal(f"no *.json vector files in {args.vectors_dir}")
    report = Report()
    cases = 0
    for path in files:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            report.error(f"{path.name}: cannot read it as JSON: {e}")
            continue
        if errors := schema_errors(doc, VECTORS_SCHEMA, path.name):
            report.errors.extend(errors)
            continue
        for i, case in enumerate(doc["cases"]):
            cases += 1
            if (claim := case.get("claim")) and claim not in ledger.by_id:
                report.error(f"{path.name}#{i}: claim {claim} is not in {ledger.path.name}")
    return report.finish(f"{args.vectors_dir}: {len(files)} files, {cases} cases valid")
