const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");
const ts = require("typescript");
const vm = require("node:vm");

function money(rate) {
  const source = readFileSync(resolve(__dirname, "../src/lib/money.ts"), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } });
  const context = { exports: {}, process: { env: { NEXT_PUBLIC_USD_TO_VND_RATE: rate } } };
  vm.runInNewContext(compiled.outputText, context);
  return context.exports;
}

test("USD products display converted VND, including fractional prices", () => {
  const { toVND, formatPrice } = money();
  assert.equal(toVND(9), 234000);
  assert.equal(toVND(12.99), 337740);
  assert.match(formatPrice(9), /234\.000/);
  assert.match(formatPrice(9), /₫/);
  assert.equal(toVND(0), 0);
});
test("VND values and mixed-currency cart totals are never converted twice", () => {
  const { toVND, formatVND } = money();
  const subtotal = toVND(9, "USD") * 2 + toVND(100000, "VND");
  assert.equal(subtotal, 568000);
  assert.match(formatVND(subtotal), /568\.000/);
});
test("rate can be configured with safe fallback for invalid configuration", () => {
  assert.equal(money("25000").toVND(9), 225000);
  for (const rate of ["", "NaN", "-1", "0", "Infinity"]) {
    assert.equal(money(rate).toVND(9), 234000);
  }
});
