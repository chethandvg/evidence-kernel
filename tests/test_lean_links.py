# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Chethan Dandebala Venkatarama

import subprocess
from pathlib import Path

import pytest
from conftest import claim

from evidence_kernel.commands.lean_links import lean_module


@pytest.fixture
def lake(monkeypatch):
    """A stand-in for ``lake env lean``: records the generated file and prints ``lake.output``."""

    class Lake:
        output, returncode, missing, seen = "", 0, False, None

    def run(command, cwd, **_kwargs):
        file = Path(cwd) / command[-1]
        Lake.seen = {"command": command, "cwd": Path(cwd), "file": file, "source": file.read_text(encoding="utf-8")}
        if Lake.missing:
            raise FileNotFoundError("lake")
        out = Lake.output.format(file=command[-1])
        return subprocess.CompletedProcess(command, Lake.returncode, stdout=out, stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    return Lake


def p_claims(ledger, tmp_path, *names):
    files = {f"proofs/{n.split('.')[0]}/Basic.lean" for n in names}
    claims = [claim(f"P{i}", "P", proof=f"proofs/{n.split('.')[0]}/Basic.lean#{n}") for i, n in enumerate(names)]
    return ledger(claims + [claim("T1")], files=files | {"tests/test_demo.py"})


def test_module_names_follow_the_path_inside_the_lake_project():
    assert lean_module("RhythmUnits/Basic.lean") == "RhythmUnits.Basic"
    assert lean_module(Path("PitchMath") / "Octave" / "Fold.lean") == "PitchMath.Octave.Fold"


def test_known_theorems_pass_and_the_temporary_file_is_deleted(ek, ledger, tmp_path, lake):
    path = p_claims(ledger, tmp_path, "RhythmUnits.period_pos", "PitchMath.fold_unique", "RhythmUnits.scale'")
    code, out, err = ek("lean-links", path)
    assert (code, err) == (0, "")
    assert "all 3 theorems found in 2 modules" in out
    assert lake.seen["command"][:3] == ["lake", "env", "lean"]
    assert lake.seen["cwd"] == (tmp_path / "proofs").resolve()
    assert lake.seen["source"] == (
        "import PitchMath.Basic\nimport RhythmUnits.Basic\n\n"
        "#check @RhythmUnits.period_pos\n#check @PitchMath.fold_unique\n#check @RhythmUnits.scale'\n"
    )
    assert not lake.seen["file"].exists()


@pytest.mark.parametrize(
    "output",
    [
        "{file}:3:7: error: unknown identifier 'RhythmUnits.period_pos'",  # lean
        "error: ./{file}:3:7: unknown constant 'RhythmUnits.period_pos'",  # lake's style
    ],
)
def test_unknown_theorems_are_mapped_back_to_claims(ek, ledger, tmp_path, lake, output):
    lake.output, lake.returncode = output + "\n{file}:4:0: warning: declaration uses 'sorry'", 1
    code, _, err = ek("lean-links", p_claims(ledger, tmp_path, "RhythmUnits.period_pos", "RhythmUnits.ok"))
    assert code == 1
    assert "demo:P0: Lean does not know RhythmUnits.period_pos" in err
    assert "demo:P1" not in err and "sorry" not in err
    assert not lake.seen["file"].exists()


def test_import_errors_name_the_claims_that_need_the_module(ek, ledger, tmp_path, lake):
    lake.output, lake.returncode = "{file}:1:0: error: unknown module prefix 'Missing'", 1
    code, _, err = ek("lean-links", p_claims(ledger, tmp_path, "Missing.thm"))
    assert code == 1
    assert "demo:P0: unknown module prefix 'Missing'" in err


def test_a_failure_without_a_diagnostic_still_fails(ek, ledger, tmp_path, lake):
    lake.output, lake.returncode = "uncaught exception: no such file or directory", 1
    code, _, err = ek("lean-links", p_claims(ledger, tmp_path, "Demo.thm"))
    assert code == 1
    assert "lake env lean exited with status 1" in err and "uncaught exception" in err


def test_a_missing_lake_fails_cleanly(ek, ledger, tmp_path, lake):
    lake.missing = True
    code, _, err = ek("lean-links", p_claims(ledger, tmp_path, "Demo.thm"))
    assert code == 1
    assert "lake is not on PATH" in err
    assert not lake.seen["file"].exists()


def test_proofs_outside_the_lake_project_fail(ek, ledger, tmp_path, lake):
    (tmp_path / "lean").mkdir()
    code, _, err = ek("lean-links", p_claims(ledger, tmp_path, "Demo.thm"), "--lake-dir", tmp_path / "lean")
    assert code == 1
    assert "demo:P0: proofs/Demo/Basic.lean is not inside the Lake project" in err
    assert lake.seen is None


def test_ledgers_without_p_claims_do_not_run_lean(ek, ledger, lake):
    code, out, _ = ek("lean-links", ledger([claim("T1")]))
    assert code == 0
    assert "no P claims to check" in out
    assert lake.seen is None
