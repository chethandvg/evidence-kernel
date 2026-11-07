# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Chethan Dandebala Venkatarama
"""evidence-kernel checks its own ledger, README and conformance vectors with its own tools."""

import json
import subprocess
import sys

import pytest
from conftest import ROOT

from evidence_kernel import __version__
from evidence_kernel.claims import CLAIMS_SCHEMA, VECTORS_SCHEMA, schema


def test_own_ledger_is_valid(ek):
    code, out, err = ek("validate", ROOT / "claims.yaml")
    assert (code, err) == (0, "")


def test_own_readme_table_is_current(ek):
    code, _, err = ek("readme-table", ROOT / "claims.yaml", ROOT / "README.md", "--check")
    assert (code, err) == (0, "")


def test_own_conformance_vectors_cite_own_claims(ek):
    code, out, err = ek("vectors", ROOT / "claims.yaml", ROOT / "conformance")
    assert (code, err) == (0, "")


@pytest.mark.parametrize("name", [CLAIMS_SCHEMA, VECTORS_SCHEMA])
def test_the_packaged_schemas_are_the_public_copies(name):
    assert schema(name) == json.loads((ROOT / "schema" / name).read_text(encoding="utf-8"))


def test_the_module_runs_as_a_command():
    done = subprocess.run([sys.executable, "-m", "evidence_kernel", "--version"], capture_output=True, text=True)
    assert (done.returncode, done.stdout.strip()) == (0, f"ek {__version__}")
