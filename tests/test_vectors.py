# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Chethan Dandebala Venkatarama

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from evidence_kernel.vectors import check_dir, compare


def test_numbers_within_tolerance_pass():
    assert compare(1 + 1e-13, 1.0, rel=1e-12) is None
    assert compare(1 + 1e-9, 1.0, rel=1e-12) is not None


def test_nested_values_compare_element_by_element():
    assert compare((69, "A4", {"c": 0.5}), [69, "A4", {"c": 0.5}]) is None
    assert compare([1, "A4"], [1, "A#4"]) is not None
    assert compare(True, 1) is not None  # booleans are not numbers


def test_runs_a_folder_including_expected_errors(tmp_path):
    doc = {
        "schema": "golden-vectors@1",
        "tolerance": {"rel": 1e-12},
        "cases": [{"fn": "inv", "args": [4], "expected": 0.25}, {"fn": "inv", "args": [0], "error": True}],
    }
    (tmp_path / "inv.json").write_text(json.dumps(doc), encoding="utf-8")

    def inv(x):
        if x == 0:
            raise ValueError("zero")
        return 1 / x

    assert check_dir(tmp_path, {"inv": inv}) == 2
    with pytest.raises(AssertionError, match="2 of 2 golden-vector cases failed"):
        check_dir(tmp_path, {"inv": lambda x: 1.0})


def test_shared_conformance_cases(tmp_path):
    """conformance/compare-cases.json: the Rust and JavaScript runners must give the same verdicts."""

    def verdict(spec):
        doc = {"schema": "golden-vectors@1", "cases": [spec["case"]]}
        if "tolerance" in spec:
            doc["tolerance"] = spec["tolerance"]
        (tmp_path / "case.json").write_text(json.dumps(doc), encoding="utf-8")

        def f(*_args):
            if spec.get("raises"):
                raise ValueError("rejected")
            return spec.get("returns")

        try:
            check_dir(tmp_path, SimpleNamespace(f=f))  # an object, as when a module is passed
        except AssertionError:
            return False
        return True

    assert check_dir(Path(__file__).resolve().parents[1] / "conformance", {"verdict": verdict}) >= 40
