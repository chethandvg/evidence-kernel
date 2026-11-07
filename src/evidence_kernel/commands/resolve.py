# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Chethan Dandebala Venkatarama
"""``ek resolve``: every cited DOI and PMID must resolve and must not be retracted or withdrawn.

DOIs are looked up in the Crossref works API, whose ``updated-by`` list carries retraction and
withdrawal notices (including those from the Retraction Watch database). A DOI that Crossref does
not hold (DataCite and Zenodo DOIs, for example) is checked against the DOI handle system; it then
resolves, but its retraction status cannot be checked. PMIDs are looked up with NCBI E-utilities
``esummary``, where the publication type "Retracted Publication" marks a retracted paper.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

from evidence_kernel import net
from evidence_kernel.claims import Report, load_ledger

CROSSREF = "https://api.crossref.org/works/{}"
HANDLES = "https://doi.org/api/handles/{}"
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&retmode=json&id={}"
PMID_BATCH = 200  # ids per esummary request
# Crossref notice types that make a work unusable as evidence. Others (corrections, expressions of
# concern) are listed in the detail column but do not fail the check.
FAILING_NOTICES = {
    "retraction": "retracted",
    "partial_retraction": "partially retracted",
    "withdrawal": "withdrawn",
    "removal": "removed",
}
TITLE_MARKS = (("RETRACTED", "retracted"), ("WITHDRAWN", "withdrawn"))


@dataclass(frozen=True)
class Lookup:
    ok: bool
    status: str
    detail: str = ""


def add_parser(commands: argparse._SubParsersAction) -> None:
    p = commands.add_parser(
        "resolve",
        help="resolve DOIs and PMIDs; fail on retractions",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("claims", type=Path, help="the claims.yaml file")
    p.set_defaults(run=run)


def run(args: argparse.Namespace) -> int:
    ledger = load_ledger(args.claims)
    cited = [
        (claim["id"], kind, str(source[kind]))
        for claim in ledger.claims
        for source in claim.get("sources", [])
        for kind in ("doi", "pmid")
        if source.get(kind)
    ]
    if not cited:
        print(f"{args.claims}: no DOIs or PMIDs to resolve")
        return 0
    results = {("doi", doi): lookup_doi(doi) for doi in dict.fromkeys(v for _, k, v in cited if k == "doi")}
    results.update(lookup_pmids(list(dict.fromkeys(v for _, k, v in cited if k == "pmid"))))

    report = Report()
    rows = []
    for claim_id, kind, value in cited:
        result = results[kind, value]
        rows.append((claim_id, f"{kind}:{value}", result.status, result.detail))
        if not result.ok:
            report.error(f"{claim_id}: {kind}:{value} is {result.status}")
    print(_table(("claim", "source", "status", "detail"), rows))
    return report.finish(f"{len(results)} sources resolved; none retracted or withdrawn")


def lookup_doi(doi: str) -> Lookup:
    try:
        work = net.fetch_json(CROSSREF.format(quote(doi, safe="/")))["message"]
    except net.FetchError as e:
        return _registered_elsewhere(doi) if e.status == 404 else Lookup(False, "lookup failed", str(e))
    except (KeyError, TypeError):
        return Lookup(False, "lookup failed", "unexpected answer from Crossref")
    notices = work.get("updated-by") or []
    title = " ".join(work.get("title") or [])
    year = ((work.get("issued") or {}).get("date-parts") or [[None]])[0][0]
    listed = [f"{n.get('type', 'update')} {n.get('DOI', '')} {_date(n)}".strip() for n in notices]
    return _judge(title, [n.get("type", "") for n in notices], _detail(year, title, listed))


def _registered_elsewhere(doi: str) -> Lookup:
    try:
        handle = net.fetch_json(HANDLES.format(quote(doi, safe="/")))
    except net.FetchError as e:
        if e.status == 404:
            return Lookup(False, "not found", "not in Crossref or the DOI system")
        return Lookup(False, "lookup failed", str(e))
    if isinstance(handle, dict) and handle.get("responseCode") == 1:
        return Lookup(True, "ok", "registered outside Crossref; retraction status not checked")
    return Lookup(False, "not found", "not in Crossref or the DOI system")


def lookup_pmids(pmids: Sequence[str]) -> dict[tuple[str, str], Lookup]:
    found: dict[tuple[str, str], Lookup] = {}
    for start in range(0, len(pmids), PMID_BATCH):
        batch = pmids[start : start + PMID_BATCH]
        try:
            answer = net.fetch_json(ESUMMARY.format(",".join(batch)))
            summaries = answer.get("result", {}) if isinstance(answer, dict) else {}
        except net.FetchError as e:
            found.update({("pmid", pmid): Lookup(False, "lookup failed", str(e)) for pmid in batch})
            continue
        for pmid in batch:
            doc: dict[str, Any] = summaries.get(pmid) or {}
            if not doc or doc.get("error"):
                found["pmid", pmid] = Lookup(False, "not found", doc.get("error") or "not in PubMed")
                continue
            title = doc.get("title") or ""
            notices = ["retraction"] if "Retracted Publication" in (doc.get("pubtype") or []) else []
            found["pmid", pmid] = _judge(title, notices, _detail((doc.get("pubdate") or "")[:4], title, []))
    return found


def _judge(title: str, notices: Iterable[str], detail: str) -> Lookup:
    """Fail on a retraction or withdrawal notice, or a title marked RETRACTED or WITHDRAWN."""
    marks = [FAILING_NOTICES[n] for n in notices if n in FAILING_NOTICES]
    marks += [status for mark, status in TITLE_MARKS if title.lstrip().upper().startswith(mark)]
    return Lookup(not marks, marks[0] if marks else "ok", detail)


def _detail(year: object, title: str, notices: list[str], width: int = 60) -> str:
    title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", title)).strip()  # Crossref titles may hold markup
    if len(title) > width:
        title = title[: width - 3].rstrip() + "..."
    return "; ".join(part for part in (f"{year or '????'} {title}".strip(), *notices) if part)


def _date(notice: dict[str, Any]) -> str:
    parts = ((notice.get("updated") or {}).get("date-parts") or [[]])[0]
    return f"({'-'.join(str(p).zfill(2) for p in parts)})" if parts else ""


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    widths = [max(len(str(cell)) for cell in column) for column in zip(headers, *rows, strict=False)]
    return "\n".join(
        "  ".join(str(cell).ljust(width) for cell, width in zip(row, widths, strict=True)).rstrip()
        for row in (headers, *rows)
    )
