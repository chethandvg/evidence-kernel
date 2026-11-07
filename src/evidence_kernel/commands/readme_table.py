# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Chethan Dandebala Venkatarama
"""``ek readme-table``: render the claims as a Markdown table between the README's markers.

The table goes between ``<!-- claims-table:start -->`` and ``<!-- claims-table:end -->``. It is a
pure function of the ledger (claims in file order), so ``--check`` can tell when it is stale.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

from evidence_kernel.claims import Fatal, Ledger, load_ledger

START, END = "<!-- claims-table:start -->", "<!-- claims-table:end -->"


def add_parser(commands: argparse._SubParsersAction) -> None:
    p = commands.add_parser(
        "readme-table",
        help="render the claims table into a README",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("claims", type=Path, help="the claims.yaml file")
    p.add_argument("readme", type=Path, help="the Markdown file with the table markers")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="exit 1 if the table in README is out of date")
    mode.add_argument("--write", action="store_true", help="update the table in README")
    p.set_defaults(run=run)


def run(args: argparse.Namespace) -> int:
    ledger = load_ledger(args.claims)
    try:
        with args.readme.open(encoding="utf-8", newline="") as f:  # keep the file's own line endings
            text = f.read()
    except OSError as e:
        raise Fatal(f"cannot read {args.readme}: {e.strerror or e}") from None
    table = render(ledger, args.readme.parent)
    updated = splice(text, table, str(args.readme))
    if args.check:
        if updated != text:
            print(
                f"error: the claims table in {args.readme} is out of date; run:\n"
                f"  ek readme-table {args.claims} {args.readme} --write",
                file=sys.stderr,
            )
            return 1
        print(f"{args.readme}: claims table is up to date")
    elif args.write:
        if updated != text:
            with args.readme.open("w", encoding="utf-8", newline="") as f:
                f.write(updated)
        print(f"{args.readme}: claims table {'updated' if updated != text else 'already up to date'}")
    else:
        print(table)
    return 0


def splice(text: str, table: str, name: str = "README") -> str:
    """Replace whatever is between the markers in ``text`` with ``table``."""
    start, end = text.find(START), text.find(END)
    if start < 0 or end < start:
        raise Fatal(f"{name} has no {START} ... {END} block")
    newline = "\r\n" if "\r\n" in text else "\n"
    return f"{text[: start + len(START)]}{newline}{table.replace(chr(10), newline)}{newline}{text[end:]}"


def render(ledger: Ledger, readme_dir: Path) -> str:
    """The Markdown table: Claim, Level, Statement, Evidence. Links are relative to ``readme_dir``."""
    if not ledger.claims:
        return "_No claims yet._"

    def link(text: str, path: str) -> str:
        href = Path(os.path.relpath(ledger.root / path, readme_dir)).as_posix()
        return f"[{text}]({quote(href, safe='/#')})"

    rows = ["| Claim | Level | Statement | Evidence |", "|---|---|---|---|"]
    for c in ledger.claims:
        rows.append(f"| `{c['id']}` | {c['level']} | {_cell(c['statement'])} | {_evidence(c, link)} |")
    return "\n".join(rows)


def _evidence(claim: dict[str, Any], link: Any) -> str:
    level = claim["level"]
    if level == "P":
        file, name = claim["proof"].split("#", 1)
        return link(f"`{name}`", file)
    if level == "V":
        return "check: " + link(f"`{claim['check']}`", claim["check"])
    if level == "T":
        return ", ".join(link(f"`{test}`", test) for test in claim["tests"])
    if level == "R":
        return "; ".join(_source(source) for source in claim["sources"])
    return f"assumption: {_cell(claim['assumption'])}"


def _source(source: dict[str, str]) -> str:
    cite = _cell(source["cite"]).replace("[", "\\[").replace("]", "\\]")
    links = []
    if doi := source.get("doi"):
        links.append(f"[doi:{_cell(doi)}](https://doi.org/{quote(doi, safe='/')})")
    if pmid := source.get("pmid"):
        links.append(f"[PMID {pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)")
    if not links and (url := source.get("url")):
        links.append(f"[link]({url})")
    return f"{cite} ({', '.join(links)})" if links else cite


def _cell(text: str) -> str:
    """Make text safe inside one table cell: one line, no column breaks."""
    return " ".join(str(text).split()).replace("|", "\\|")
