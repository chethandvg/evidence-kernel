# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Chethan Dandebala Venkatarama

import io
from urllib.error import HTTPError, URLError

import pytest

from evidence_kernel import __version__, net


@pytest.fixture
def server(monkeypatch):
    """Replace urlopen with a queue of answers (bytes or exceptions); record requests and sleeps."""
    state = {"answers": [], "requests": [], "sleeps": []}

    def urlopen(request, timeout):
        state["requests"].append((request, timeout))
        answer = state["answers"].pop(0)
        if isinstance(answer, Exception):
            raise answer
        return io.BytesIO(answer)

    monkeypatch.setattr(net, "urlopen", urlopen)
    monkeypatch.setattr(net, "sleep", state["sleeps"].append)
    return state


def http_error(code):
    return HTTPError("https://api.crossref.org/works/x", code, "error", None, None)


def test_requests_identify_the_tool_without_personal_data(server):
    server["answers"] = [b'{"ok": true}']
    assert net.fetch_json("https://api.crossref.org/works/x") == {"ok": True}
    request, timeout = server["requests"][0]
    assert (
        request.get_header("User-agent")
        == f"evidence-kernel/{__version__} (+https://github.com/chethandvg/evidence-kernel)"
    )
    assert "@" not in request.get_header("User-agent")
    assert timeout == net.TIMEOUT


def test_transient_failures_are_retried_with_back_off(server):
    server["answers"] = [http_error(503), URLError("reset"), b"done"]
    assert net.fetch("https://api.crossref.org/works/x") == b"done"
    assert len(server["requests"]) == 3
    assert {2, 4} <= set(server["sleeps"])  # back-off between attempts


def test_permanent_failures_are_not_retried(server):
    server["answers"] = [http_error(404)]
    with pytest.raises(net.FetchError, match=r"api\.crossref\.org: HTTP 404") as raised:
        net.fetch("https://api.crossref.org/works/x")
    assert raised.value.status == 404
    assert len(server["requests"]) == 1


def test_retries_are_limited(server):
    server["answers"] = [TimeoutError("slow")] * (net.RETRIES + 1)
    with pytest.raises(net.FetchError, match="network error"):
        net.fetch("https://api.crossref.org/works/x")
    assert len(server["requests"]) == net.RETRIES + 1


def test_requests_are_spaced_out(server, monkeypatch):
    monkeypatch.setattr(net, "_last_request", net.monotonic())
    server["answers"] = [b"[]"]
    net.fetch("https://eutils.ncbi.nlm.nih.gov/x")
    assert 0 < server["sleeps"][0] <= net.DELAY


def test_answers_that_are_not_json_fail(server):
    server["answers"] = [b"<html>"]
    with pytest.raises(net.FetchError, match="not JSON"):
        net.fetch_json("https://api.crossref.org/works/x")


def test_read_takes_paths_and_urls(server, tmp_path):
    (tmp_path / "r.json").write_bytes(b"{}")
    assert net.read(str(tmp_path / "r.json")) == b"{}"  # a Windows drive letter is not a URL scheme
    with pytest.raises(net.FetchError):
        net.read(tmp_path / "missing.json")
    server["answers"] = [b"remote"]
    assert net.read("https://raw.githubusercontent.com/x") == b"remote"
