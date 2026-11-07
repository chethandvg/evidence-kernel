# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Chethan Dandebala Venkatarama
"""The ``ek`` (or ``evidence-kernel``) command line."""

from __future__ import annotations

import argparse
import io
import sys
from collections.abc import Sequence

from evidence_kernel import __version__
from evidence_kernel.claims import Fatal, fail
from evidence_kernel.commands import lean_links, readme_table, resolve, validate, vectors

COMMANDS = (validate, resolve, lean_links, readme_table, vectors)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ek",
        description="Check a claims ledger (claims.yaml): every claim says how it is known.",
        epilog="Levels: P proved in Lean, V verified numerics, T tested, R referenced (DOI or PMID), M assumed.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    for command in COMMANDS:
        command.add_parser(commands)
    for subparser in commands.choices.values():  # module docstrings are the help text; drop reST quoting
        subparser.description = (subparser.description or "").replace("``", "`")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # never crash on a character the console cannot show
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="replace")
    args = build_parser().parse_args(argv)
    try:
        return args.run(args)
    except Fatal as e:
        return fail(e.messages)
