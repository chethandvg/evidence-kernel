# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Chethan Dandebala Venkatarama
"""Shared helpers for the ``ek`` commands: schemas, ledgers, claim references and reporting."""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache, cached_property
from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

CLAIMS_SCHEMA = "claims.schema.json"
VECTORS_SCHEMA = "golden-vectors.schema.json"

_REF = re.compile(r"(?P<id>(?P<prefix>[a-z][a-z0-9-]*):[A-Z0-9][A-Z0-9-]*)@(?P<major>[0-9]+)")
_MAJOR = re.compile(r"([0-9]+)\.")


class Fatal(Exception):
    """A problem that stops a command; ``ek`` prints each message and exits with status 1."""

    def __init__(self, *messages: str) -> None:
        super().__init__(*messages)
        self.messages = messages


@cache
def schema(name: str) -> dict[str, Any]:
    """Load a packaged JSON Schema: ``claims.schema.json`` or ``golden-vectors.schema.json``."""
    packaged = resources.files("evidence_kernel") / "schema" / name
    if packaged.is_file():
        return json.loads(packaged.read_text(encoding="utf-8"))
    # Source checkout or editable install: the public copy at the repository root.
    return json.loads((Path(__file__).resolve().parents[2] / "schema" / name).read_text(encoding="utf-8"))


@cache
def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(schema(name), format_checker=Draft202012Validator.FORMAT_CHECKER)


def schema_errors(doc: Any, name: str, where: str) -> list[str]:
    """Every way ``doc`` breaks the named schema, as ``where: location: message`` lines."""
    errors = sorted(_validator(name).iter_errors(doc), key=lambda e: (e.json_path, e.message))
    return [f"{where}: {_locate(doc, list(e.absolute_path))}: {e.message}" for e in errors]


def _locate(doc: Any, path: list[str | int]) -> str:
    text = "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in path).lstrip(".") or "top level"
    if len(path) >= 2 and path[0] == "claims" and isinstance(path[1], int):
        claim = doc["claims"][path[1]]
        if isinstance(claim, dict) and isinstance(claim.get("id"), str):
            text += f" ({claim['id']})"
    return text


def load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as e:
        raise Fatal(f"cannot read {path}: {e.strerror or e}") from None
    except yaml.YAMLError as e:
        raise Fatal(f"{path} is not valid YAML: {e}") from None


@dataclass
class Ledger:
    """A claims ledger that has passed schema validation."""

    path: Path
    doc: dict[str, Any]

    @property
    def root(self) -> Path:
        """The repository root: every path in a ledger is relative to the ledger's folder."""
        return self.path.parent

    @property
    def prefix(self) -> str:
        return self.doc["prefix"]

    @property
    def claims(self) -> list[dict[str, Any]]:
        return self.doc["claims"]

    @cached_property
    def by_id(self) -> dict[str, dict[str, Any]]:
        return {claim["id"]: claim for claim in self.claims}


def load_ledger(path: str | Path) -> Ledger:
    """Read a ``claims.yaml`` file; raise :class:`Fatal` listing every schema error."""
    path = Path(path)
    doc = load_yaml(path)
    if errors := schema_errors(doc, CLAIMS_SCHEMA, path.name):
        raise Fatal(*errors)
    return Ledger(path, doc)


def parse_ref(ref: str) -> tuple[str, str, int]:
    """Split a dependency ``prefix:NAME@major`` into (prefix, claim id, major version)."""
    m = _REF.fullmatch(ref)
    if not m:
        raise ValueError(f"not a claim reference (prefix:NAME@major): {ref!r}")
    return m["prefix"], m["id"], int(m["major"])


def major_version(version: object) -> int | None:
    """The major part of a ``MAJOR.MINOR.PATCH`` version, or None if there is none."""
    m = _MAJOR.match(str(version))
    return int(m[1]) if m else None


class Report:
    """Collects errors and warnings, then prints them and gives the exit status."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def finish(self, success: str) -> int:
        """Print warnings and errors to stderr (or ``success`` to stdout); return 1 if there were errors."""
        sys.stdout.flush()  # keep anything already printed (such as a table) ahead of the messages
        for message in self.warnings:
            print(f"warning: {message}", file=sys.stderr)
        for message in self.errors:
            print(f"error: {message}", file=sys.stderr)
        if self.errors:
            n = len(self.errors)
            print(f"{n} error{'s' if n != 1 else ''}", file=sys.stderr)
            return 1
        print(success)
        return 0


def fail(messages: Sequence[str]) -> int:
    """Report ``messages`` as errors and return the failing exit status."""
    report = Report()
    for message in messages:
        report.error(message)
    return report.finish("")
