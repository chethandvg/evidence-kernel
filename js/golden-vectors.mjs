// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Chethan Dandebala Venkatarama
//
// Run shared JSON golden vectors (golden-vectors@1) against a JavaScript or
// WebAssembly implementation. The Rust crate `golden-vectors` and the Python
// module `evidence_kernel.vectors` apply the same rules to the same files.
//
//   import { checkDir } from "golden-vectors";
//   checkDir(new URL("../vectors/", import.meta.url), impl); // impl: { fnName: Function }
//
// Numbers (IEEE-754 doubles) pass when |got - expected| <= max(abs, rel * |expected|); strings,
// booleans and null must match exactly; arrays (including typed arrays) and
// objects are compared element by element. A case with "error": true passes
// only if the function throws.

import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const isNumber = (x) => typeof x === "number" || typeof x === "bigint";
const normalise = (x) => (ArrayBuffer.isView(x) ? Array.from(x) : typeof x === "bigint" ? Number(x) : x);

/** Returns a description of the first difference between got and want, or null. */
export function compare(got, want, rel = 0, abs = 0, at = "value") {
  got = normalise(got);
  if (isNumber(got) && isNumber(want)) {
    return got === want || Math.abs(got - want) <= Math.max(abs, rel * Math.abs(want))
      ? null
      : `${at}: got ${got}, expected ${want}`;
  }
  if (Array.isArray(got) && Array.isArray(want)) {
    if (got.length !== want.length) return `${at}: got ${got.length} items, expected ${want.length}`;
    for (let i = 0; i < want.length; i++) {
      const msg = compare(got[i], want[i], rel, abs, `${at}[${i}]`);
      if (msg) return msg;
    }
    return null;
  }
  if (got && want && typeof got === "object" && typeof want === "object" && !Array.isArray(got) && !Array.isArray(want)) {
    const [g, w] = [Object.keys(got).sort(), Object.keys(want).sort()];
    if (g.join() !== w.join()) return `${at}: got keys ${g}, expected ${w}`;
    for (const k of w) {
      const msg = compare(got[k], want[k], rel, abs, `${at}.${k}`);
      if (msg) return msg;
    }
    return null;
  }
  return got === want ? null : `${at}: got ${JSON.stringify(got)}, expected ${JSON.stringify(want)}`;
}

/**
 * Runs every case in every *.json file of `dir` (a path or file: URL) against
 * `impl`, an object whose properties are the functions. Returns the number of
 * cases checked; throws an Error listing every failing case.
 */
export function checkDir(dir, impl) {
  const folder = dir instanceof URL ? fileURLToPath(dir) : dir;
  const failures = [];
  let checked = 0;
  for (const file of readdirSync(folder).filter((f) => f.endsWith(".json")).sort()) {
    const doc = JSON.parse(readFileSync(join(folder, file), "utf8"));
    if (doc.schema !== "golden-vectors@1") throw new Error(`${file}: schema must be golden-vectors@1`);
    doc.cases.forEach((c, i) => {
      const at = `${file}#${i} ${c.fn}(${c.args.map((a) => JSON.stringify(a)).join(", ")})`;
      const tol = { rel: 0, abs: 0, ...doc.tolerance, ...c.tolerance };
      checked++;
      // An inherited Object.prototype member (such as `constructor`) is not an implementation.
      const fn = Object.hasOwn(impl, c.fn) || !(c.fn in Object.prototype) ? impl[c.fn] : undefined;
      if (typeof fn !== "function") return failures.push(`${at}: no implementation named ${c.fn}`);
      let got;
      try {
        got = fn(...c.args);
      } catch (e) {
        if (!c.error) failures.push(`${at}: unexpected error: ${e}`);
        return;
      }
      if (c.error) return failures.push(`${at}: expected an error, got ${JSON.stringify(normalise(got))}`);
      const msg = compare(got, c.expected, tol.rel, tol.abs, at);
      if (msg) failures.push(msg);
    });
  }
  if (!checked) throw new Error(`no golden-vector cases found in ${folder}`);
  if (failures.length) throw new Error(`${failures.length} of ${checked} golden-vector cases failed:\n${failures.join("\n")}`);
  return checked;
}
