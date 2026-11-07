# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Chethan Dandebala Venkatarama

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from evidence_kernel import net
from evidence_kernel.cli import main

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """No test may reach the network."""

    def refuse(*_args, **_kwargs):
        raise AssertionError("tests must not use the network")

    monkeypatch.setattr(net, "urlopen", refuse)


@pytest.fixture
def ek(capsys):
    """Run ``ek`` with arguments; return (exit status, stdout, stderr)."""

    def run(*argv):
        code = main([str(a) for a in argv])
        out, err = capsys.readouterr()
        return code, out, err

    return run


@pytest.fixture
def ledger(tmp_path):
    """Write claims.yaml (and empty evidence files) into a temporary repo; return its path."""

    def write(claims, prefix="demo", files=(), folder=tmp_path):
        for name in files:
            (folder / name).parent.mkdir(parents=True, exist_ok=True)
            (folder / name).write_text("", encoding="utf-8")
        doc = {"schema": "evidence-kernel/claims@1", "repo": f"{prefix}-repo", "prefix": prefix, "claims": claims}
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "claims.yaml"
        path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return path

    return write


@pytest.fixture
def web(monkeypatch):
    """A fake internet for net.fetch: set ``web.pages[url]`` to a JSON value, bytes or an HTTP status."""
    fake = SimpleNamespace(pages={}, calls=[])

    def fetch(url, accept="application/json"):
        fake.calls.append(url)
        page = fake.pages.get(url, 404)
        if isinstance(page, int):
            raise net.FetchError(url, f"HTTP {page}", page)
        return page if isinstance(page, bytes) else json.dumps(page).encode()

    monkeypatch.setattr(net, "fetch", fetch)
    return fake


def claim(name, level="T", prefix="demo", **fields):
    """A minimal valid claim of the given level."""
    evidence = {
        "P": {"proof": "proofs/Demo/Basic.lean#Demo.thm"},
        "V": {"check": "checks/interval.py"},
        "T": {"tests": ["tests/test_demo.py"]},
        "R": {"sources": [{"cite": "Taylor et al. 1993, Human Reproduction", "doi": "10.1093/demo.1"}]},
        "M": {"assumption": "Cells are well mixed."},
    }[level]
    return {"id": f"{prefix}:{name}", "version": "1.0.0", "level": level, "statement": f"{name} holds."} | {
        **evidence,
        **fields,
    }


EVIDENCE_FILES = ("proofs/Demo/Basic.lean", "checks/interval.py", "tests/test_demo.py")
