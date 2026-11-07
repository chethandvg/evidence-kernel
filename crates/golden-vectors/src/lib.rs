// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Chethan Dandebala Venkatarama

//! Run shared JSON golden vectors (`golden-vectors@1`) against a Rust
//! implementation.
//!
//! A vector file lists cases `{fn, args, expected | error}`. Your test maps
//! each `fn` name to your code with a `dispatch` function; [`check_dir`] runs
//! every case in every `*.json` file of a folder and fails with a list of all
//! mismatches. Numbers are read as the nearest IEEE-754 double (serde_json's
//! `float_roundtrip` feature, as in Python and JavaScript) and pass when
//! `|got - expected| <= max(abs, rel * |expected|)`; strings, booleans and
//! nulls must match exactly; arrays and objects are compared element by
//! element. The shared cases in `conformance/compare-cases.json` hold every
//! runner to the same verdicts.

use serde_json::Value;
use std::fmt::Display;
use std::path::Path;

/// What an implementation returned for one case.
#[derive(Debug, Clone, PartialEq)]
pub enum Outcome {
    /// A result to compare with `expected`.
    Value(Value),
    /// The implementation rejected the input (expected when the case has `"error": true`).
    Error(String),
    /// No implementation is registered for the case's `fn`.
    Unknown(String),
}

impl Outcome {
    /// Wraps a plain (infallible) result.
    pub fn value(v: impl Into<Value>) -> Self {
        Self::Value(v.into())
    }

    /// The fallback arm of a `dispatch` match.
    pub fn unknown(name: &str, args: &[Value]) -> Self {
        Self::Unknown(format!(
            "no implementation registered for `{name}` ({} args)",
            args.len()
        ))
    }
}

impl<T: Into<Value>, E: Display> From<Result<T, E>> for Outcome {
    fn from(r: Result<T, E>) -> Self {
        match r {
            Ok(v) => Self::Value(v.into()),
            Err(e) => Self::Error(e.to_string()),
        }
    }
}

/// Argument `i` as `f64`. Panics with a clear message if it is missing or not a number.
pub fn f64_arg(args: &[Value], i: usize) -> f64 {
    args.get(i)
        .and_then(Value::as_f64)
        .unwrap_or_else(|| panic!("argument {i} must be a number, got {:?}", args.get(i)))
}

/// Argument `i` as `i64`. Panics with a clear message if it is missing or not an integer.
pub fn i64_arg(args: &[Value], i: usize) -> i64 {
    args.get(i)
        .and_then(Value::as_i64)
        .unwrap_or_else(|| panic!("argument {i} must be an integer, got {:?}", args.get(i)))
}

/// Argument `i` as `&str`. Panics with a clear message if it is missing or not a string.
pub fn str_arg(args: &[Value], i: usize) -> &str {
    args.get(i)
        .and_then(Value::as_str)
        .unwrap_or_else(|| panic!("argument {i} must be a string, got {:?}", args.get(i)))
}

#[derive(Clone, Copy)]
struct Tolerance {
    rel: f64,
    abs: f64,
}

impl Tolerance {
    fn from_json(v: Option<&Value>, default: Self) -> Self {
        let field = |k: &str, d: f64| {
            v.and_then(|t| t.get(k))
                .and_then(Value::as_f64)
                .unwrap_or(d)
        };
        Self {
            rel: field("rel", default.rel),
            abs: field("abs", default.abs),
        }
    }
}

/// Compares `got` with `want`; returns a description of the first difference.
fn compare(got: &Value, want: &Value, tol: Tolerance, at: &str) -> Result<(), String> {
    match (got, want) {
        (Value::Number(g), Value::Number(w)) => {
            let (g, w) = (
                g.as_f64().unwrap_or(f64::NAN),
                w.as_f64().unwrap_or(f64::NAN),
            );
            if g == w || (g - w).abs() <= tol.abs.max(tol.rel * w.abs()) {
                Ok(())
            } else {
                Err(format!(
                    "{at}: got {g:e}, expected {w:e} (rel {:e})",
                    ((g - w) / w).abs()
                ))
            }
        }
        (Value::Array(g), Value::Array(w)) => {
            if g.len() != w.len() {
                return Err(format!("{at}: got {} items, expected {}", g.len(), w.len()));
            }
            g.iter()
                .zip(w)
                .enumerate()
                .try_for_each(|(i, (g, w))| compare(g, w, tol, &format!("{at}[{i}]")))
        }
        (Value::Object(g), Value::Object(w)) => {
            if g.len() != w.len() || w.keys().any(|k| !g.contains_key(k)) {
                return Err(format!(
                    "{at}: got keys {:?}, expected {:?}",
                    g.keys().collect::<Vec<_>>(),
                    w.keys().collect::<Vec<_>>()
                ));
            }
            w.iter()
                .try_for_each(|(k, w)| compare(&g[k], w, tol, &format!("{at}.{k}")))
        }
        _ if got == want => Ok(()),
        _ => Err(format!("{at}: got {got}, expected {want}")),
    }
}

/// Runs every case in every `*.json` file of `dir` through `dispatch`.
///
/// Returns the number of cases checked. Panics, listing every failing case,
/// if any case fails, if a file is malformed, or if no cases were found.
pub fn check_dir(dir: impl AsRef<Path>, dispatch: impl Fn(&str, &[Value]) -> Outcome) -> usize {
    let dir = dir.as_ref();
    let mut paths: Vec<_> = std::fs::read_dir(dir)
        .unwrap_or_else(|e| panic!("cannot read vectors folder {}: {e}", dir.display()))
        .filter_map(|entry| entry.ok().map(|e| e.path()))
        .filter(|p| p.extension().is_some_and(|ext| ext == "json"))
        .collect();
    paths.sort();

    let (mut checked, mut failures) = (0, Vec::new());
    for path in &paths {
        let name = path
            .file_name()
            .map_or_else(String::new, |n| n.to_string_lossy().into_owned());
        let text =
            std::fs::read_to_string(path).unwrap_or_else(|e| panic!("cannot read {name}: {e}"));
        let doc: Value =
            serde_json::from_str(&text).unwrap_or_else(|e| panic!("{name} is not valid JSON: {e}"));
        assert_eq!(
            doc["schema"], "golden-vectors@1",
            "{name}: schema must be golden-vectors@1"
        );
        let file_tol = Tolerance::from_json(doc.get("tolerance"), Tolerance { rel: 0.0, abs: 0.0 });
        let cases = doc["cases"]
            .as_array()
            .unwrap_or_else(|| panic!("{name}: `cases` must be an array"));

        for (i, case) in cases.iter().enumerate() {
            let func = case["fn"]
                .as_str()
                .unwrap_or_else(|| panic!("{name}#{i}: `fn` must be a string"));
            let args = case["args"]
                .as_array()
                .unwrap_or_else(|| panic!("{name}#{i}: `args` must be an array"));
            let at = format!(
                "{name}#{i} {func}({})",
                args.iter()
                    .map(Value::to_string)
                    .collect::<Vec<_>>()
                    .join(", ")
            );
            let tol = Tolerance::from_json(case.get("tolerance"), file_tol);
            let wants_error = case.get("error") == Some(&Value::Bool(true));
            let result = match (dispatch(func, args), wants_error) {
                (Outcome::Unknown(msg), _) => Err(format!("{at}: {msg}")),
                (Outcome::Error(_), true) => Ok(()),
                (Outcome::Value(v), true) => Err(format!("{at}: expected an error, got {v}")),
                (Outcome::Error(e), false) => Err(format!("{at}: unexpected error: {e}")),
                (Outcome::Value(v), false) => compare(&v, &case["expected"], tol, &at),
            };
            if let Err(msg) = result {
                failures.push(msg);
            }
            checked += 1;
        }
    }
    assert!(
        checked > 0,
        "no golden-vector cases found in {}",
        dir.display()
    );
    assert!(
        failures.is_empty(),
        "{} of {checked} golden-vector cases failed:\n{}",
        failures.len(),
        failures.join("\n")
    );
    checked
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    const EXACT: Tolerance = Tolerance { rel: 0.0, abs: 0.0 };

    #[test]
    fn numbers_within_tolerance_pass() {
        let tol = Tolerance {
            rel: 1e-12,
            abs: 0.0,
        };
        assert!(compare(&json!(1.0 + 1e-13), &json!(1.0), tol, "x").is_ok());
        assert!(compare(&json!(1.0 + 1e-9), &json!(1.0), tol, "x").is_err());
    }

    #[test]
    fn nested_values_compare_element_by_element() {
        assert!(
            compare(
                &json!([1, "A4", {"c": 0.5}]),
                &json!([1.0, "A4", {"c": 0.5}]),
                EXACT,
                "x"
            )
            .is_ok()
        );
        assert!(compare(&json!([1, "A4"]), &json!([1, "A#4"]), EXACT, "x").is_err());
        assert!(compare(&json!([1]), &json!([1, 2]), EXACT, "x").is_err());
    }

    #[test]
    fn runs_a_folder_and_reports_every_failure() {
        let dir = std::env::temp_dir().join(format!("golden-vectors-test-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let doc = json!({"schema": "golden-vectors@1", "tolerance": {"rel": 1e-12}, "cases": [
            {"fn": "inv", "args": [4.0], "expected": 0.25},
            {"fn": "inv", "args": [0.0], "error": true}
        ]});
        std::fs::write(dir.join("inv.json"), doc.to_string()).unwrap();
        let inv = |name: &str, args: &[Value]| match name {
            "inv" => {
                let x = f64_arg(args, 0);
                Outcome::from(if x == 0.0 { Err("zero") } else { Ok(1.0 / x) })
            }
            _ => Outcome::unknown(name, args),
        };
        assert_eq!(check_dir(&dir, inv), 2);
        let wrong = std::panic::catch_unwind(|| {
            check_dir(&dir, |_: &str, _: &[Value]| Outcome::value(1.0))
        });
        std::fs::remove_dir_all(&dir).unwrap();
        assert!(wrong.is_err());
    }

    /// `conformance/compare-cases.json`: the Python and JavaScript runners must give the same verdicts.
    #[test]
    fn shared_conformance_cases() {
        let dir =
            std::env::temp_dir().join(format!("golden-vectors-conformance-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let verdict = |spec: &Value| {
            let mut doc = json!({"schema": "golden-vectors@1", "cases": [spec["case"]]});
            if let Some(tolerance) = spec.get("tolerance") {
                doc["tolerance"] = tolerance.clone();
            }
            std::fs::write(dir.join("case.json"), doc.to_string()).unwrap();
            let outcome = if spec.get("raises") == Some(&Value::Bool(true)) {
                Outcome::Error("rejected".into())
            } else {
                Outcome::Value(spec["returns"].clone())
            };
            std::panic::catch_unwind(|| {
                check_dir(&dir, |name: &str, args: &[Value]| match name {
                    "f" => outcome.clone(),
                    _ => Outcome::unknown(name, args),
                })
            })
            .is_ok()
        };
        let conformance = concat!(env!("CARGO_MANIFEST_DIR"), "/../../conformance");
        let checked = check_dir(conformance, |name: &str, args: &[Value]| match name {
            "verdict" => Outcome::value(verdict(&args[0])),
            _ => Outcome::unknown(name, args),
        });
        std::fs::remove_dir_all(&dir).unwrap();
        assert!(checked >= 40);
    }
}
