# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Chethan Dandebala Venkatarama

import json

import pytest
from conftest import EVIDENCE_FILES, claim

from evidence_kernel.commands.validate import DEFAULT_REGISTRY, RAW_CLAIMS


def test_a_ledger_with_every_level_and_a_local_dependency_is_valid(ek, ledger, web):
    path = ledger(
        [claim(name, level) for name, level in [("P1", "P"), ("V1", "V"), ("R1", "R"), ("M1", "M")]]
        + [claim("T1", depends_on=["demo:P1@1", "demo:R1@1"])],
        files=EVIDENCE_FILES,
    )
    code, out, err = ek("validate", path)
    assert (code, err) == (0, "")
    assert "5 claims valid" in out
    assert web.calls == []  # no cross-repo dependency, so the registry is never fetched


def test_schema_errors_name_the_claim(ek, ledger):
    broken = claim("P1", "P")
    del broken["proof"]
    code, _, err = ek("validate", ledger([broken, claim("T1", version="1.0")]))
    assert code == 1
    assert "claims[0] (demo:P1): 'proof' is a required property" in err
    assert "claims[1].version (demo:T1): '1.0' does not match" in err


@pytest.mark.parametrize("text", ["claims: [unclosed", None])
def test_unreadable_or_invalid_yaml_fails(ek, tmp_path, text):
    path = tmp_path / "claims.yaml"
    if text is not None:
        path.write_text(text, encoding="utf-8")
    code, _, err = ek("validate", path)
    assert code == 1
    assert ("not valid YAML" if text else "cannot read") in err


def test_semantic_errors_are_all_reported(ek, ledger):
    claims = [
        claim("P1", "P"),  # proof file missing
        claim("V1", "V"),  # check file missing
        claim("T1", tests=["tests/missing.py"]),
        claim("T1"),  # duplicate id
        claim("OTHER", prefix="elsewhere"),  # wrong prefix for this ledger (and so a cross-repo claim)
        claim("R1", "R", sources=[{"cite": "A web page", "url": "https://example.org/"}]),
        claim("T2", depends_on=["demo:NOPE@1", "demo:P1@2"]),
    ]
    code, _, err = ek("validate", ledger(claims, files=["tests/test_demo.py"]))
    assert code == 1
    for message in [
        "demo:P1: proof proofs/Demo/Basic.lean does not exist",
        "demo:V1: check checks/interval.py does not exist",
        "demo:T1: test tests/missing.py does not exist",
        "demo:T1 is used by 2 claims; ids must be unique",
        "elsewhere:OTHER does not use this ledger's prefix 'demo:'",
        "demo:R1: an R claim needs at least one source with a doi or pmid",
        "demo:T2 depends on demo:NOPE@1, which is not in claims.yaml",
        "demo:T2 depends on demo:P1@2, but claims.yaml has it at version 1.0.0",
    ]:
        assert message in err
    assert "8 errors" in err


REGISTRY = {
    "repos": [
        {"name": "rhythm-units", "claim_prefix": "rhythm", "status": "released"},
        {"name": "pitch-math", "claim_prefix": "pitch", "status": "building"},
        {"name": "dynamics-core", "claim_prefix": "dynamics", "status": "planned"},
        {"name": "hub", "status": "building"},  # no claim prefix
    ]
}


def test_cross_repo_dependencies_use_the_local_checkout(ek, ledger, tmp_path, web):
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps(REGISTRY), encoding="utf-8")
    ledger([claim("TIME-SCALING", prefix="rhythm", version="1.2.0")], prefix="rhythm", folder=tmp_path / "rhythm-units")
    path = ledger(
        [claim("OK", depends_on=["rhythm:TIME-SCALING@1"]), claim("OLD", depends_on=["rhythm:TIME-SCALING@2"])],
        files=EVIDENCE_FILES,
        folder=tmp_path / "pitch-math",
    )
    code, _, err = ek("validate", path, "--registry", registry, "--local-root", tmp_path)
    assert code == 1
    assert "demo:OLD depends on rhythm:TIME-SCALING@2, but rhythm-units/claims.yaml has it at version 1.2.0" in err
    assert "demo:OK" not in err
    assert web.calls == []


def test_cross_repo_dependencies_are_fetched_from_github(ek, ledger, web):
    web.pages[DEFAULT_REGISTRY] = REGISTRY
    web.pages[RAW_CLAIMS.format(name="rhythm-units")] = b"claims:\n  - {id: 'rhythm:TIME-SCALING', version: 1.0.0}\n"
    path = ledger([claim("A", depends_on=["rhythm:TIME-SCALING@1", "rhythm:GONE@1"])], files=EVIDENCE_FILES)
    code, _, err = ek("validate", path)
    assert code == 1
    assert "demo:A depends on rhythm:GONE@1, which is not in rhythm-units/claims.yaml" in err
    assert "TIME-SCALING" not in err
    assert web.calls == [DEFAULT_REGISTRY, RAW_CLAIMS.format(name="rhythm-units")]


def test_unpublished_repos_only_warn_but_published_ones_must_be_reachable(ek, ledger, web):
    web.pages[DEFAULT_REGISTRY] = REGISTRY
    path = ledger([claim("A", depends_on=["pitch:X@1", "dynamics:Y@1"])], files=EVIDENCE_FILES)
    code, out, err = ek("validate", path)
    assert code == 0
    assert "warning: pitch:X@1 not checked: pitch-math/claims.yaml is not available yet (status building" in err
    assert "warning: dynamics:Y@1 not checked" in err
    assert "1 claims valid" in out

    path = ledger([claim("A", depends_on=["rhythm:X@1"])], files=EVIDENCE_FILES)
    code, _, err = ek("validate", path)
    assert code == 1
    assert "cannot fetch rhythm-units/claims.yaml (raw.githubusercontent.com: HTTP 404); needed for rhythm:X@1" in err


def test_unknown_prefixes_and_a_missing_registry_fail(ek, ledger, tmp_path, web):
    web.pages[DEFAULT_REGISTRY] = REGISTRY
    path = ledger([claim("A", depends_on=["nobody:X@1"])], files=EVIDENCE_FILES)
    code, _, err = ek("validate", path)
    assert code == 1
    assert "no repo in the registry has the claim prefix 'nobody' (needed for nobody:X@1)" in err

    code, _, err = ek("validate", path, "--registry", tmp_path / "missing.json")
    assert code == 1
    assert "cannot load the registry" in err
