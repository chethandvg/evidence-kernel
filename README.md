# Evidence kernel

**A claims ledger in which every claim states how it is known, with DOI and retraction checks and cross-language golden-vector test runners.**

[![CI](https://github.com/chethandvg/evidence-kernel/actions/workflows/ci.yml/badge.svg)](https://github.com/chethandvg/evidence-kernel/actions/workflows/ci.yml)
[![Licence](https://img.shields.io/badge/licence-Apache--2.0-blue)](LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24035685.svg)](https://doi.org/10.5281/zenodo.24035685)

Part of **[Frequencies of Life](https://chethandvg.github.io/frequencies-of-life/)**, open code for the rhythms of life in which every claim says how it is known: proved, verified, tested, referenced or assumed.

## What is proved

<!-- claims-table:start -->
| Claim | Level | Statement | Evidence |
|---|---|---|---|
| `evidence:RUNNERS-AGREE` | T | The Rust, Python and JavaScript golden-vector runners give the same verdict on every shared conformance case: numbers inside and outside tolerance, nested arrays and objects, strings, booleans versus numbers, null, and expected or unexpected errors. | [`conformance/compare-cases.json`](conformance/compare-cases.json), [`crates/golden-vectors/src/lib.rs`](crates/golden-vectors/src/lib.rs), [`tests/test_vectors.py`](tests/test_vectors.py), [`js/golden-vectors.test.mjs`](js/golden-vectors.test.mjs) |
| `evidence:LEDGER-CHECKED` | T | `ek validate` rejects a ledger that breaks the claims@1 schema, repeats an id, uses another repo's prefix, points to a missing proof, check or test file, has an R claim without a DOI or PMID, or depends on a claim that is missing or at another major version. | [`tests/test_validate.py`](tests/test_validate.py) |
| `evidence:RETRACTIONS-FAIL` | T | `ek resolve` exits with an error when a cited DOI or PMID does not resolve, or when Crossref or PubMed marks it as retracted or withdrawn. | [`tests/test_resolve.py`](tests/test_resolve.py) |
| `evidence:LEAN-NAMES-EXIST` | T | `ek lean-links` reports every P claim whose theorem Lean does not know, and always deletes its temporary Lean file. | [`tests/test_lean_links.py`](tests/test_lean_links.py) |
| `evidence:README-TABLE-CURRENT` | T | The README claims table depends only on `claims.yaml`, and `ek readme-table --check` fails whenever the table is out of date. | [`tests/test_readme_table.py`](tests/test_readme_table.py) |
| `evidence:VECTORS-CHECKED` | T | `ek vectors` rejects a vector file that breaks the golden-vectors@1 schema or cites a claim that is not in the ledger. | [`tests/test_vectors_cmd.py`](tests/test_vectors_cmd.py), [`tests/test_self.py`](tests/test_self.py) |
<!-- claims-table:end -->

Levels: **P** machine-checked proof (Lean 4) · **V** verified numerics · **T** tested · **R** referenced (DOI or PMID) · **M** model assumption.

## Use

### The `ek` command

```bash
pip install "evidence-kernel @ git+https://github.com/chethandvg/evidence-kernel@v0.1.0"
```

This installs one tool under two names, `ek` and `evidence-kernel` (Python 3.10 or later). Every command reads a `claims.yaml` ledger, whose paths are relative to the ledger's own folder, and exits with status 1 when a check fails.

| Command | What it checks |
|---|---|
| `ek validate claims.yaml` | The claims@1 schema ([`schema/claims.schema.json`](schema/claims.schema.json)); unique ids that use the ledger's prefix; proof, check and test files that exist; a DOI or PMID for every R claim; and every `depends_on` claim, at the stated major version. |
| `ek resolve claims.yaml` | Every DOI resolves (Crossref) and every PMID resolves (PubMed), and none is retracted or withdrawn. |
| `ek lean-links claims.yaml --lake-dir proofs` | Every P claim's theorem exists in the built Lean project. |
| `ek readme-table claims.yaml README.md --check` | The table between `<!-- claims-table:start -->` and `<!-- claims-table:end -->` matches the ledger. `--write` updates it. |
| `ek vectors claims.yaml vectors` | Every golden-vector file matches golden-vectors@1 ([`schema/golden-vectors.schema.json`](schema/golden-vectors.schema.json)) and cites only claims in the ledger. |

A ledger lists claims with their level and evidence:

```yaml
schema: evidence-kernel/claims@1
repo: pitch-math
prefix: pitch
claims:
  - id: pitch:OCTAVE-FOLD-UNIQUE
    version: 1.0.0
    level: P
    statement: "For every f > 0 and a > 0 there is exactly one integer n with a ≤ f·2^n < 2a."
    proof: proofs/PitchMath/OctaveFold.lean#PitchMath.octave_fold_unique
    depends_on: [rhythm:TIME-SCALING@1]
```

**Dependencies on other repos.** `rhythm:TIME-SCALING@1` names a claim in another repo by its prefix. `ek validate` finds the repo with that `claim_prefix` in the [registry](https://github.com/chethandvg/.github/blob/main/registry.json) and reads its `claims.yaml` from GitHub, or from `DIR/<repo>/claims.yaml` when you pass `--local-root DIR`. A repo that has not published its ledger yet (registry status `planned` or `building`) gives a warning instead of an error.

```bash
ek validate claims.yaml --registry ../.github/registry.json --local-root ..
```

**Retractions.** `ek resolve` reads Crossref's `updated-by` notices (which include the Retraction Watch database) and PubMed's publication types. A DOI that Crossref does not hold, such as a Zenodo DOI, is checked in the DOI handle system: it resolves, but its retraction status cannot be checked, and the table says so. This is a real run on three references from the project's report:

```text
claim                      source                                     status     detail
bio:HUMAN-CA-OSCILLATIONS  doi:10.1093/oxfordjournals.humrep.a137999  ok         1993 Fertilization and early embryology: Oscillations in intra...
bio:SPERM-STEERING         doi:10.1126/sciadv.aba5168                 retracted  2020 Human sperm uses asymmetric and anisotropic flagellar con...; retraction 10.1126/sciadv.aau9116 (2021-05-01); expression_of_concern 10.1126/sciadv.abe3154 (2020-08-14)
bio:SPERM-STEERING         pmid:32789171                              retracted  2020 RETRACTED: Human sperm uses asymmetric and anisotropic fl...
bio:ACOUSTIC-SLEEP         doi:10.1111/jsr.13385                      retracted  2021 RETRACTED: The impact of acoustic stimulation during slee...; retraction 10.1111/jsr.70111 (2025-06-16)
error: bio:SPERM-STEERING: doi:10.1126/sciadv.aba5168 is retracted
error: bio:SPERM-STEERING: pmid:32789171 is retracted
error: bio:ACOUSTIC-SLEEP: doi:10.1111/jsr.13385 is retracted
3 errors
```

Requests carry the User-Agent `evidence-kernel/<version> (+https://github.com/chethandvg/evidence-kernel)`, wait 0.4 s between calls and retry a timeout, HTTP 429 or a 5xx answer twice.

**Lean names.** `ek lean-links` turns `proofs/RhythmUnits/Basic.lean#RhythmUnits.period_pos` into `import RhythmUnits.Basic` and `#check @RhythmUnits.period_pos`, runs all claims through one `lake env lean` call in the Lake folder, and maps any "unknown identifier" back to its claim. Build the project first (`lake build`).

### Golden-vector runners

A vector file lists inputs and the outputs that every implementation must give:

```json
{
  "schema": "golden-vectors@1",
  "tolerance": { "rel": 1e-12 },
  "cases": [
    { "claim": "rhythm:TIME-SCALING", "fn": "hz_from_period", "args": [600], "expected": 0.0016666666666666668 },
    { "fn": "hz_from_period", "args": [0], "error": true }
  ]
}
```

The same folder of vectors runs in three languages.

**Rust** (`Cargo.toml`: `golden-vectors = { git = "https://github.com/chethandvg/evidence-kernel", tag = "v0.1.0" }` and `serde_json = "1"` under `[dev-dependencies]`):

```rust
use golden_vectors::{Outcome, f64_arg};
use serde_json::Value;

fn dispatch(name: &str, args: &[Value]) -> Outcome {
    match name {
        "hz_from_period" => Outcome::from(my_crate::hz_from_period(f64_arg(args, 0))),
        _ => Outcome::unknown(name, args),
    }
}

#[test]
fn golden_vectors() {
    golden_vectors::check_dir(concat!(env!("CARGO_MANIFEST_DIR"), "/vectors"), dispatch);
}
```

**Python** (`pip install` as above):

```python
from pathlib import Path

import my_module
from evidence_kernel.vectors import check_dir


def test_golden_vectors():
    assert check_dir(Path(__file__).parent / "vectors", my_module) > 0
```

**JavaScript or WebAssembly** (`npm install --save-dev github:chethandvg/evidence-kernel#v0.1.0`):

```js
import { test } from "node:test";
import { checkDir } from "golden-vectors";
import * as impl from "../pkg/my_module.js";

test("golden vectors", () => {
  checkDir(new URL("../vectors/", import.meta.url), impl);
});
```

The rules are the same everywhere:

- Numbers are IEEE-754 doubles and pass when |got − expected| ≤ max(abs, rel × |expected|). A case's `tolerance` overrides the file's, field by field; without one, numbers must be equal.
- Strings, booleans and null must match exactly. A boolean is never a number.
- Arrays are compared element by element, and objects key by key in any order. An array never equals an object.
- A case with `"error": true` passes only if the function raises, throws or returns `Err`.

## How it is verified

- **One rulebook, three runners:** [`conformance/compare-cases.json`](conformance/compare-cases.json) holds 47 shared cases (tolerances, nested values, strings, booleans against numbers, null and error cases). The Rust, Python and JavaScript test suites all run it and must give the same verdict on every case.
- **Python:** pytest on Linux and Windows with Python 3.10, 3.12 and 3.14, plus Ruff lint and format checks. The tests never use the network: Crossref, PubMed, GitHub and `lake` are replaced by stand-ins, including failure cases.
- **Rust:** `cargo fmt --check`, `cargo clippy -- -D warnings` and `cargo test` on Linux and Windows.
- **JavaScript:** `node --test` on Node 24.
- **Claims:** this repo's own [`claims.yaml`](claims.yaml) is checked by its own `ek` (validate, resolve, README table) on every push and weekly, to catch newly retracted sources, and the table above is generated by `ek readme-table`.

## Cite

If you use this work, please cite it. GitHub's **Cite this repository** button gives APA and BibTeX from [CITATION.cff](CITATION.cff).

## Licence

Code: Apache-2.0 ([LICENSE](LICENSE)). Copyright notices are in [NOTICE](NOTICE).
