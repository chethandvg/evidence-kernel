# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Chethan Dandebala Venkatarama

import pytest
from conftest import claim

from evidence_kernel.commands.resolve import CROSSREF, ESUMMARY, HANDLES


def crossref(title, year=2020, notices=()):
    work = {"title": [title], "issued": {"date-parts": [[year, 7, 1]]}}
    if notices:
        work["updated-by"] = [
            {"type": kind, "DOI": f"10.1/{kind}", "updated": {"date-parts": [[2021, 5, 1]]}} for kind in notices
        ]
    return {"status": "ok", "message": work}


def pubmed(**docs):
    return {"result": {"uids": list(docs), **docs}}


def ledger_citing(ledger, *sources):
    return ledger([claim(f"R{i}", "R", sources=[s]) for i, s in enumerate(sources)])


def test_resolved_sources_print_a_table_and_pass(ek, ledger, web):
    web.pages[CROSSREF.format("10.1093/humrep.1")] = crossref("Oscillations in <i>human</i> oocytes", 1993)
    web.pages[ESUMMARY.format("8449444")] = pubmed(**{"8449444": {"title": "A paper.", "pubdate": "1993 Dec"}})
    path = ledger_citing(
        ledger,
        {"cite": "Taylor 1993", "doi": "10.1093/humrep.1", "pmid": "8449444"},
        {"cite": "Taylor 1993 again", "doi": "10.1093/humrep.1"},
    )
    code, out, err = ek("resolve", path)
    assert (code, err) == (0, "")
    lines = out.splitlines()
    assert lines[0].split() == ["claim", "source", "status", "detail"]
    assert lines[1].split()[:4] == ["demo:R0", "doi:10.1093/humrep.1", "ok", "1993"]
    assert "Oscillations in human oocytes" in lines[1]  # markup removed
    assert lines[2].split()[:3] == ["demo:R0", "pmid:8449444", "ok"]
    assert "2 sources resolved" in out
    assert len(web.calls) == 2  # the repeated DOI is looked up once


@pytest.mark.parametrize(
    ("work", "status"),
    [
        (crossref("Human sperm steering", notices=["retraction", "expression_of_concern"]), "retracted"),
        (crossref("A review", notices=["withdrawal"]), "withdrawn"),
        (crossref("RETRACTED: The impact of acoustic stimulation"), "retracted"),
    ],
)
def test_retracted_or_withdrawn_dois_fail(ek, ledger, web, work, status):
    web.pages[CROSSREF.format("10.1126/x")] = work
    code, out, err = ek("resolve", ledger_citing(ledger, {"cite": "X", "doi": "10.1126/x"}))
    assert code == 1
    assert f"demo:R0: doi:10.1126/x is {status}" in err
    if "updated-by" in work["message"]:
        assert f"{work['message']['updated-by'][0]['type']} 10.1/" in out and "(2021-05-01)" in out


def test_notices_that_are_not_retractions_are_shown_but_pass(ek, ledger, web):
    web.pages[CROSSREF.format("10.1000/eoc")] = crossref("Fine paper", notices=["expression_of_concern", "correction"])
    code, out, _ = ek("resolve", ledger_citing(ledger, {"cite": "X", "doi": "10.1000/eoc"}))
    assert code == 0
    assert "expression_of_concern 10.1/expression_of_concern (2021-05-01); correction" in out


def test_dois_outside_crossref_resolve_through_the_handle_system(ek, ledger, web):
    web.pages[HANDLES.format("10.5281/zenodo.1")] = {"responseCode": 1, "handle": "10.5281/zenodo.1"}
    code, out, err = ek(
        "resolve",
        ledger_citing(ledger, {"cite": "Data", "doi": "10.5281/zenodo.1"}, {"cite": "Y", "doi": "10.9999/none"}),
    )
    assert code == 1
    assert "registered outside Crossref; retraction status not checked" in out
    assert "demo:R1: doi:10.9999/none is not found" in err
    assert "demo:R0" not in err


def test_pubmed_retractions_and_unknown_ids_fail(ek, ledger, web):
    web.pages[ESUMMARY.format("32789171,1")] = pubmed(
        **{
            "32789171": {"title": "Human sperm.", "pubtype": ["Journal Article", "Retracted Publication"]},
            "1": {"error": "cannot get document summary"},
        }
    )
    code, _, err = ek("resolve", ledger_citing(ledger, {"cite": "A", "pmid": "32789171"}, {"cite": "B", "pmid": "1"}))
    assert code == 1
    assert "demo:R0: pmid:32789171 is retracted" in err
    assert "demo:R1: pmid:1 is not found" in err


def test_lookups_that_fail_are_errors(ek, ledger, web):
    web.pages[CROSSREF.format("10.1000/down")] = 503
    web.pages[ESUMMARY.format("2")] = 500
    code, out, err = ek(
        "resolve", ledger_citing(ledger, {"cite": "A", "doi": "10.1000/down"}, {"cite": "B", "pmid": "2"})
    )
    assert code == 1
    assert "doi:10.1000/down is lookup failed" in err and "pmid:2 is lookup failed" in err
    assert "api.crossref.org: HTTP 503" in out


def test_a_ledger_without_sources_needs_no_network(ek, ledger, web):
    code, out, _ = ek("resolve", ledger([claim("T1")]))
    assert code == 0
    assert "no DOIs or PMIDs to resolve" in out
    assert web.calls == []
