// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Chethan Dandebala Venkatarama

import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { checkDir, compare } from "./golden-vectors.mjs";

test("numbers within tolerance pass", () => {
  assert.equal(compare(1 + 1e-13, 1, 1e-12), null);
  assert.notEqual(compare(1 + 1e-9, 1, 1e-12), null);
});

test("typed arrays and objects compare element by element", () => {
  assert.equal(compare(new Float64Array([1, 2]), [1, 2]), null);
  assert.equal(compare({ midi: 69, name: "A4" }, { name: "A4", midi: 69 }), null);
  assert.notEqual(compare([1, "A4"], [1, "A#4"]), null);
});

test("runs a folder, including expected errors", () => {
  const dir = mkdtempSync(join(tmpdir(), "golden-vectors-"));
  writeFileSync(join(dir, "inv.json"), JSON.stringify({
    schema: "golden-vectors@1",
    tolerance: { rel: 1e-12 },
    cases: [{ fn: "inv", args: [4], expected: 0.25 }, { fn: "inv", args: [0], error: true }],
  }));
  const inv = (x) => { if (x === 0) throw new Error("zero"); return 1 / x; };
  try {
    assert.equal(checkDir(dir, { inv }), 2);
    assert.throws(() => checkDir(dir, { inv: () => 1 }), /2 of 2 golden-vector cases failed/);
  } finally {
    rmSync(dir, { recursive: true });
  }
});

test("shared conformance cases (conformance/compare-cases.json)", () => {
  const dir = mkdtempSync(join(tmpdir(), "golden-vectors-conformance-"));
  const verdict = ({ tolerance, case: c, returns, raises }) => {
    writeFileSync(join(dir, "case.json"), JSON.stringify({ schema: "golden-vectors@1", ...(tolerance && { tolerance }), cases: [c] }));
    const f = () => {
      if (raises) throw new Error("rejected");
      return returns;
    };
    try {
      checkDir(dir, { f });
      return true;
    } catch {
      return false;
    }
  };
  try {
    assert.ok(checkDir(new URL("../conformance/", import.meta.url), { verdict }) >= 40);
  } finally {
    rmSync(dir, { recursive: true });
  }
});
