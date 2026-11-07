# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Chethan Dandebala Venkatarama
"""Run shared JSON golden vectors (golden-vectors@1) against a Python implementation.

The Rust crate ``golden-vectors`` and the JavaScript module ``golden-vectors``
apply exactly the same rules to the same files, so one set of vectors shows
that every binding gives the same answers.

    from evidence_kernel.vectors import check_dir
    import my_module

    def test_golden_vectors():
        assert check_dir(Path(__file__).parent / "vectors", my_module) > 0

Numbers are compared as IEEE-754 doubles (as ``JSON.parse`` and serde_json read
them) and pass when ``|got - expected| <= max(abs, rel * |expected|)``; strings,
booleans and ``None`` must match exactly; tuples and lists are compared element
by element, and so are dicts. A case with ``"error": true`` passes only if the
implementation raises an exception.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

Impl = Mapping[str, Callable[..., Any]] | Any


def _number(x: Any) -> bool:
    return isinstance(x, int | float) and not isinstance(x, bool)


def compare(got: Any, want: Any, rel: float = 0.0, abs_: float = 0.0, at: str = "value") -> str | None:
    """Return a description of the first difference between ``got`` and ``want``, or None."""
    if _number(got) and _number(want):
        g, w = float(got), float(want)  # doubles, as in the Rust and JavaScript runners
        if g == w or abs(g - w) <= max(abs_, rel * abs(w)):
            return None
        return f"{at}: got {got!r}, expected {want!r}"
    if isinstance(got, list | tuple) and isinstance(want, list):
        if len(got) != len(want):
            return f"{at}: got {len(got)} items, expected {len(want)}"
        for i, (g, w) in enumerate(zip(got, want, strict=True)):
            if msg := compare(g, w, rel, abs_, f"{at}[{i}]"):
                return msg
        return None
    if isinstance(got, Mapping) and isinstance(want, Mapping):
        if set(got) != set(want):
            return f"{at}: got keys {sorted(got)}, expected {sorted(want)}"
        for k, w in want.items():
            if msg := compare(got[k], w, rel, abs_, f"{at}.{k}"):
                return msg
        return None
    return None if got == want and type(got) is type(want) else f"{at}: got {got!r}, expected {want!r}"


def _lookup(impl: Impl, name: str) -> Callable[..., Any] | None:
    if isinstance(impl, Mapping):
        return impl.get(name)
    return None if name.startswith("__") else getattr(impl, name, None)  # never a built-in such as __init__


def check_dir(directory: str | Path, impl: Impl) -> int:
    """Run every case in every ``*.json`` file of ``directory`` against ``impl``.

    ``impl`` is a module (or any object) whose attributes are the functions, or a
    mapping from name to function. Returns the number of cases checked; raises
    ``AssertionError`` listing every failing case.
    """
    directory = Path(directory)
    checked, failures = 0, []
    for path in sorted(directory.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("schema") != "golden-vectors@1":
            raise AssertionError(f"{path.name}: schema must be golden-vectors@1")
        file_tol = doc.get("tolerance", {})
        for i, case in enumerate(doc["cases"]):
            func, args = case["fn"], case["args"]
            at = f"{path.name}#{i} {func}({', '.join(json.dumps(a) for a in args)})"
            tol = {**file_tol, **case.get("tolerance", {})}
            checked += 1
            fn = _lookup(impl, func)
            if fn is None:
                failures.append(f"{at}: no implementation named {func!r}")
                continue
            try:
                got = fn(*args)
            except Exception as e:  # noqa: BLE001 - any exception means "rejected the input"
                if not case.get("error"):
                    failures.append(f"{at}: unexpected error: {e!r}")
                continue
            if case.get("error"):
                failures.append(f"{at}: expected an error, got {got!r}")
            elif msg := compare(got, case["expected"], tol.get("rel", 0.0), tol.get("abs", 0.0), at):
                failures.append(msg)
    # Raise explicitly rather than with `assert`, so that `python -O` cannot skip the checks.
    if not checked:
        raise AssertionError(f"no golden-vector cases found in {directory}")
    if failures:
        raise AssertionError(f"{len(failures)} of {checked} golden-vector cases failed:\n" + "\n".join(failures))
    return checked
