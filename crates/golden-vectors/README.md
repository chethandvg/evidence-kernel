# golden-vectors (Rust)

Runs shared JSON golden vectors (`golden-vectors@1`) against a Rust implementation. The Python (`evidence_kernel.vectors`) and JavaScript (`golden-vectors`) runners in [evidence-kernel](https://github.com/chethandvg/evidence-kernel) read the same files with the same rules, so one set of vectors proves that every binding agrees.

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
