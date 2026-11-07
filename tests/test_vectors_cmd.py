# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Chethan Dandebala Venkatarama

import json

from conftest import claim


def vectors(tmp_path, **files):
    folder = tmp_path / "vectors"
    folder.mkdir(exist_ok=True)
    for name, doc in files.items():
        (folder / f"{name}.json").write_text(doc if isinstance(doc, str) else json.dumps(doc), encoding="utf-8")
    return folder


def doc(*cases):
    return {"schema": "golden-vectors@1", "tolerance": {"rel": 1e-12}, "cases": list(cases)}


def test_valid_vectors_citing_known_claims_pass(ek, ledger, tmp_path):
    folder = vectors(
        tmp_path,
        hz=doc(
            {"claim": "demo:T1", "fn": "hz", "args": [600], "expected": 0.0016},
            {"fn": "hz", "args": [0], "error": True},
        ),
    )
    code, out, err = ek("vectors", ledger([claim("T1")]), folder)
    assert (code, err) == (0, "")
    assert "1 files, 2 cases valid" in out


def test_schema_errors_unknown_claims_and_bad_json_fail(ek, ledger, tmp_path):
    folder = vectors(
        tmp_path,
        a_both=doc({"fn": "hz", "args": [1], "expected": 1, "error": True}),
        b_name=doc({"fn": "Hz", "args": [1], "expected": 1}),
        c_claim=doc({"claim": "demo:NOPE", "fn": "hz", "args": [1], "expected": 1}),
        d_json="{not json",
        e_schema={"schema": "golden-vectors@2", "cases": []},
    )
    code, _, err = ek("vectors", ledger([claim("T1")]), folder)
    assert code == 1
    assert "a_both.json: cases[0]: " in err  # expected and error together break oneOf
    assert "b_name.json: cases[0].fn: 'Hz' does not match" in err
    assert "c_claim.json#0: claim demo:NOPE is not in claims.yaml" in err
    assert "d_json.json: cannot read it as JSON" in err
    assert "e_schema.json: schema: 'golden-vectors@1' was expected" in err
    assert "e_schema.json: cases: [] should be non-empty" in err


def test_an_empty_folder_fails(ek, ledger, tmp_path):
    code, _, err = ek("vectors", ledger([claim("T1")]), vectors(tmp_path))
    assert code == 1
    assert "no *.json vector files" in err
