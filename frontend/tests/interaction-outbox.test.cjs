const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");
const { webcrypto } = require("node:crypto");
const ts = require("typescript");

const source = readFileSync(path.join(__dirname, "../src/lib/recommendations-client.ts"), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: {
  target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS,
} }).outputText;

function storage() {
  const values = new Map();
  return {
    getItem(key) { return values.get(key) ?? null; },
    setItem(key, value) { values.set(key, value); },
    removeItem(key) { values.delete(key); },
  };
}

function runtime(localStorage, sessionStorage, fetch) {
  const exports = {};
  const context = {
    exports, localStorage, sessionStorage, fetch, crypto: webcrypto,
    URL, AbortSignal, Event,
    window: { location: { origin: "http://example.test" }, dispatchEvent() {} },
  };
  vm.runInNewContext(compiled, context, { filename: "recommendations-client.ts" });
  return exports;
}

test("failed write survives a new JS runtime and is committed before the home feed", async () => {
  const local = storage();
  const session = storage();
  local.setItem("merrec_token", "test-token");
  local.setItem("merrec_user", JSON.stringify({ id: "user-1" }));
  const first = runtime(local, session, async () => ({ ok: false, status: 503 }));
  assert.equal(await first.trackEventClient({ item_id: "42", event_type: "view" }), false);
  const pending = JSON.parse(local.getItem("merrec_interactions:user-1"));
  assert.equal(pending.length, 1);
  assert.equal(pending[0].item_id, "42");
  assert.ok(pending[0].event_key);

  const calls = [];
  const second = runtime(local, session, async (url, options) => {
    calls.push({ url: String(url), options });
    if (options.method === "POST") return { ok: true, json: async () => ({ status: "success", event_id: "1" }) };
    return { ok: true, json: async () => ({ request_id: "req", model_name: "hybrid_feature_ranker_v2", items: [] }) };
  });
  const result = await second.fetchRecommendationsClient("home");
  assert.equal(result.request_id, "req");
  assert.equal(calls.length, 2);
  assert.ok(calls[0].url.endsWith("/api/events"));
  assert.ok(calls[1].url.includes("/api/recommendations"));
  assert.equal(JSON.parse(calls[0].options.body).event_key, pending[0].event_key);
  assert.equal(calls[0].options.headers.Authorization, "Bearer test-token");
  assert.equal(JSON.parse(local.getItem("merrec_interactions:user-1")).length, 0);
});

test("home feed stops when an interaction cannot be committed", async () => {
  const local = storage();
  const session = storage();
  let calls = 0;
  const client = runtime(local, session, async () => { calls += 1; return { ok: false, status: 503 }; });
  await client.trackEventClient({ item_id: "43", event_type: "cart" });
  await assert.rejects(client.fetchRecommendationsClient("home"), /chưa được lưu/);
  assert.equal(calls, 2);
  assert.equal(client.pendingInteractionCount(), 1);
});
