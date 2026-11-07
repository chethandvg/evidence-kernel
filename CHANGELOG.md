# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-11-07

### Added

- The `ek` command line (also installed as `evidence-kernel`):
  - `ek validate`: the claims@1 schema, unique ids with the ledger's prefix, existing proof, check and test files, a DOI or PMID for every R claim, and same-repo and cross-repo `depends_on` checks through the registry.
  - `ek resolve`: DOIs through Crossref (with a DOI handle fallback) and PMIDs through PubMed; fails on unresolvable, retracted or withdrawn sources.
  - `ek lean-links`: checks every P claim's theorem with one `lake env lean` run.
  - `ek readme-table`: renders the README claims table; `--check` and `--write`.
  - `ek vectors`: checks golden-vector files against golden-vectors@1 and the ledger.
- The claims@1 and golden-vectors@1 JSON Schemas, also packaged inside the wheel.
- Golden-vector runners for Rust (`golden-vectors` crate), Python (`evidence_kernel.vectors`) and JavaScript or WebAssembly (`golden-vectors` module).
- `conformance/compare-cases.json`: 47 shared cases that all three runners must pass. While writing them, the runners were brought into line: Rust reads numbers with correct rounding (serde_json `float_roundtrip`); Python compares numbers as doubles and ignores dunder attributes; JavaScript no longer matches an array with an object or treats `Object.prototype` members as implementations; the Python runner raises instead of using `assert`, so `python -O` cannot skip it.
- This repo's own `claims.yaml` (six T claims) and its generated README table.
- CI jobs for Python, Rust and JavaScript, and a claims check that uses this repo's own `ek`.
