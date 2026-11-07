# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Chethan Dandebala Venkatarama
"""Polite HTTP GET with the standard library: a generic User-Agent, timeouts, a few retries and a delay."""

from __future__ import annotations

import json
from http.client import HTTPException
from pathlib import Path
from time import monotonic, sleep
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from evidence_kernel import __version__

USER_AGENT = f"evidence-kernel/{__version__} (+https://github.com/chethandvg/evidence-kernel)"
TIMEOUT = 30  # seconds for each request
RETRIES = 2  # extra attempts after a network error, HTTP 429 or a 5xx answer
DELAY = 0.4  # seconds between requests, so at most 2.5 per second
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
_last_request = float("-inf")


class FetchError(Exception):
    """A URL or file could not be read. ``status`` is the HTTP status code, if there was one."""

    def __init__(self, location: str, reason: str, status: int | None = None) -> None:
        super().__init__(f"{urlsplit(location).netloc if is_url(location) else location}: {reason}")
        self.location, self.status = location, status


def is_url(location: str) -> bool:
    return urlsplit(location).scheme in ("http", "https")


def fetch(url: str, accept: str = "application/json") -> bytes:
    """GET ``url``, waiting between requests and retrying transient failures."""
    global _last_request
    for attempt in range(RETRIES + 1):
        if (wait := DELAY - (monotonic() - _last_request)) > 0:
            sleep(wait)
        _last_request = monotonic()
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
        try:
            with urlopen(request, timeout=TIMEOUT) as response:
                return response.read()
        except HTTPError as e:
            if e.code not in _RETRY_STATUS or attempt == RETRIES:
                raise FetchError(url, f"HTTP {e.code}", e.code) from None
        except (OSError, HTTPException) as e:  # DNS failure, refused or dropped connection, timeout
            if attempt == RETRIES:
                raise FetchError(url, f"network error ({getattr(e, 'reason', None) or e})") from None
        sleep(2 * (attempt + 1))
    raise AssertionError("unreachable")


def fetch_json(url: str) -> Any:
    body = fetch(url)
    try:
        return json.loads(body)
    except ValueError:
        raise FetchError(url, "the answer is not JSON") from None


def read(location: str | Path, accept: str = "*/*") -> bytes:
    """Read a local file, or fetch an http(s) URL."""
    if isinstance(location, str) and is_url(location):
        return fetch(location, accept)
    try:
        return Path(location).read_bytes()
    except OSError as e:
        raise FetchError(str(location), e.strerror or str(e)) from None
