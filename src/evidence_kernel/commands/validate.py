# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Chethan Dandebala Venkatarama
"""``ek validate``: check a ledger against claims@1, its evidence files and the claims it depends on."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml

from evidence_kernel import net
from evidence_kernel.claims import Fatal, Ledger, Report, load_ledger, major_version, parse_ref

DEFAULT_REGISTRY = "https://raw.githubusercontent.com/chethandvg/.github/main/registry.json"
RAW_CLAIMS = "https://raw.githubusercontent.com/chethandvg/{name}/main/claims.yaml"
NOT_YET_PUBLISHED = frozenset({"planned", "building"})

Claims = dict[str, dict[str, Any]]


def add_parser(commands: argparse._SubParsersAction) -> None:
    p = commands.add_parser("validate", help="check schema, evidence files and dependencies", description=__doc__)
    p.add_argument("claims", type=Path, help="the claims.yaml file (paths in it are relative to its folder)")
    p.add_argument(
        "--registry",
        default=DEFAULT_REGISTRY,
        metavar="URL|PATH",
        help="registry.json that maps claim prefixes to repos (default: %(default)s)",
    )
    p.add_argument(
        "--local-root", type=Path, metavar="DIR", help="use DIR/<repo>/claims.yaml, when present, instead of GitHub"
    )
    p.set_defaults(run=run)


def run(args: argparse.Namespace) -> int:
    ledger = load_ledger(args.claims)
    report = Report()
    _check_ids(ledger, report)
    _check_evidence(ledger, report)
    _check_dependencies(ledger, report, _Upstream(args.registry, args.local_root, report))
    return report.finish(f"{args.claims}: {len(ledger.claims)} claims valid")


def _check_ids(ledger: Ledger, report: Report) -> None:
    for claim_id, count in Counter(claim["id"] for claim in ledger.claims).items():
        if count > 1:
            report.error(f"{claim_id} is used by {count} claims; ids must be unique")
    for claim in ledger.claims:
        if claim["id"].partition(":")[0] != ledger.prefix:
            report.error(f"{claim['id']} does not use this ledger's prefix '{ledger.prefix}:'")


def _check_evidence(ledger: Ledger, report: Report) -> None:
    for claim in ledger.claims:
        paths = [("proof", claim["proof"].partition("#")[0])] if "proof" in claim else []
        paths += [("check", claim["check"])] if "check" in claim else []
        paths += [("test", test) for test in claim.get("tests", [])]
        for kind, path in paths:
            if not (ledger.root / path).exists():
                report.error(f"{claim['id']}: {kind} {path} does not exist")
        if claim["level"] == "R" and not any(s.get("doi") or s.get("pmid") for s in claim["sources"]):
            report.error(f"{claim['id']}: an R claim needs at least one source with a doi or pmid")


def _check_dependencies(ledger: Ledger, report: Report, upstream: _Upstream) -> None:
    foreign: dict[str, list[tuple[str, str, str, int]]] = defaultdict(list)
    for claim in ledger.claims:
        for ref in claim.get("depends_on", []):
            prefix, target, major = parse_ref(ref)
            if prefix == ledger.prefix:
                _check_target(report, claim["id"], ref, ledger.by_id.get(target), major, ledger.path.name)
            else:
                foreign[prefix].append((claim["id"], ref, target, major))
    for prefix, refs in sorted(foreign.items()):
        if found := upstream.claims(prefix, [ref for _, ref, _, _ in refs]):
            where, claims = found
            for claim_id, ref, target, major in refs:
                _check_target(report, claim_id, ref, claims.get(target), major, where)


def _check_target(report: Report, claim_id: str, ref: str, target: dict | None, major: int, where: str) -> None:
    if target is None:
        report.error(f"{claim_id} depends on {ref}, which is not in {where}")
    elif major_version(target.get("version")) != major:
        report.error(f"{claim_id} depends on {ref}, but {where} has it at version {target.get('version')}")


class _Upstream:
    """Other repos' ledgers, found through the registry. Each prefix is looked up once."""

    def __init__(self, registry: str, local_root: Path | None, report: Report) -> None:
        self.registry, self.local_root, self.report = registry, local_root, report
        self._repos: dict[str, dict[str, Any]] | None = None

    def _repo(self, prefix: str) -> dict[str, Any] | None:
        if self._repos is None:  # fetched only when some claim depends on another repo
            try:
                doc = json.loads(net.read(self.registry))
            except (net.FetchError, ValueError) as e:
                raise Fatal(f"cannot load the registry {self.registry}: {e}") from None
            repos = doc.get("repos", []) if isinstance(doc, dict) else []
            self._repos = {r["claim_prefix"]: r for r in repos if isinstance(r, dict) and r.get("claim_prefix")}
        return self._repos.get(prefix)

    def claims(self, prefix: str, refs: list[str]) -> tuple[str, Claims] | None:
        needed = ", ".join(refs)
        repo = self._repo(prefix)
        if repo is None:
            self.report.error(f"no repo in the registry has the claim prefix '{prefix}' (needed for {needed})")
            return None
        name, where = repo["name"], f"{repo['name']}/claims.yaml"
        local = self.local_root / name / "claims.yaml" if self.local_root else None
        try:
            doc = yaml.safe_load(net.read(local if local and local.is_file() else RAW_CLAIMS.format(name=name)))
        except net.FetchError as e:
            status = repo.get("status")
            if status in NOT_YET_PUBLISHED:
                self.report.warn(f"{needed} not checked: {where} is not available yet (status {status}; {e})")
            else:
                self.report.error(f"cannot fetch {where} ({e}); needed for {needed}")
            return None
        except yaml.YAMLError as e:
            self.report.error(f"{where} is not valid YAML: {e}")
            return None
        claims = doc.get("claims") if isinstance(doc, dict) else None
        if not isinstance(claims, list):
            self.report.error(f"{where} has no list of claims; needed for {needed}")
            return None
        return where, {c["id"]: c for c in claims if isinstance(c, dict) and isinstance(c.get("id"), str)}
