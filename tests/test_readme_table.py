# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Chethan Dandebala Venkatarama

from conftest import claim

from evidence_kernel.claims import load_ledger
from evidence_kernel.commands.readme_table import END, START, render

CLAIMS = [
    claim("P1", "P"),
    claim("V1", "V"),
    claim("T1", tests=["tests/test_demo.py", "vectors/a b.json"], statement="Pipes | and\nnewlines stay in one cell."),
    claim(
        "R1",
        "R",
        sources=[
            {"cite": "Taylor et al. 1993, Human Reproduction", "doi": "10.1093/demo.1", "pmid": "8449444"},
            {"cite": "PubMed only [abstract]", "pmid": "1"},
        ],
    ),
    claim("M1", "M"),
]

TABLE = "\n".join(
    [
        "| Claim | Level | Statement | Evidence |",
        "|---|---|---|---|",
        "| `demo:P1` | P | P1 holds. | [`Demo.thm`](proofs/Demo/Basic.lean) |",
        "| `demo:V1` | V | V1 holds. | check: [`checks/interval.py`](checks/interval.py) |",
        r"| `demo:T1` | T | Pipes \| and newlines stay in one cell. | "
        "[`tests/test_demo.py`](tests/test_demo.py), [`vectors/a b.json`](vectors/a%20b.json) |",
        "| `demo:R1` | R | R1 holds. | Taylor et al. 1993, Human Reproduction "
        "([doi:10.1093/demo.1](https://doi.org/10.1093/demo.1), "
        "[PMID 8449444](https://pubmed.ncbi.nlm.nih.gov/8449444/)); "
        r"PubMed only \[abstract\] ([PMID 1](https://pubmed.ncbi.nlm.nih.gov/1/)) |",
        "| `demo:M1` | M | M1 holds. | assumption: Cells are well mixed. |",
    ]
)


def readme(tmp_path, body="", newline="\n", name="README.md"):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    text = f"# Demo{newline}{newline}{START}{newline}{body}{END}{newline}{newline}More text.{newline}"
    path.write_bytes(text.encode())
    return path


def test_the_table_has_one_row_per_claim_with_its_evidence(ledger, tmp_path):
    assert render(load_ledger(ledger(CLAIMS)), tmp_path) == TABLE


def test_links_are_relative_to_the_readme(ledger, tmp_path):
    table = render(load_ledger(ledger([claim("P1", "P")])), tmp_path / "docs")
    assert "[`Demo.thm`](../proofs/Demo/Basic.lean)" in table


def test_an_empty_ledger_says_so(ledger, tmp_path):
    assert render(load_ledger(ledger([])), tmp_path) == "_No claims yet._"


def test_check_fails_until_write_updates_the_table(ek, ledger, tmp_path):
    path, md = ledger(CLAIMS), readme(tmp_path, "| stale |\n")
    code, _, err = ek("readme-table", path, md, "--check")
    assert code == 1
    assert "out of date" in err and "--write" in err

    assert ek("readme-table", path, md, "--write")[:2] == (0, f"{md}: claims table updated\n")
    first = md.read_bytes()
    assert first == f"# Demo\n\n{START}\n{TABLE}\n{END}\n\nMore text.\n".encode()
    assert ek("readme-table", path, md, "--write")[1] == f"{md}: claims table already up to date\n"
    assert md.read_bytes() == first  # deterministic: a second write changes nothing
    assert ek("readme-table", path, md, "--check")[0] == 0


def test_windows_line_endings_are_kept(ek, ledger, tmp_path):
    path, md = ledger(CLAIMS[:2]), readme(tmp_path, newline="\r\n")
    assert ek("readme-table", path, md, "--write")[0] == 0
    text = md.read_bytes().decode()
    assert text.count("\r\n") == text.count("\n") == 10  # every line ending is CRLF
    assert ek("readme-table", path, md, "--check")[0] == 0


def test_without_a_flag_the_table_is_printed(ek, ledger, tmp_path):
    md = readme(tmp_path)
    code, out, _ = ek("readme-table", ledger(CLAIMS), md)
    assert (code, out) == (0, TABLE + "\n")
    assert START + "\n" + END in md.read_text(encoding="utf-8")  # untouched


def test_a_readme_without_markers_fails(ek, ledger, tmp_path):
    md = tmp_path / "README.md"
    md.write_text("# No table here\n", encoding="utf-8")
    code, _, err = ek("readme-table", ledger(CLAIMS), md, "--check")
    assert code == 1
    assert "has no <!-- claims-table:start -->" in err
    assert ek("readme-table", ledger(CLAIMS), tmp_path / "missing.md")[0] == 1
