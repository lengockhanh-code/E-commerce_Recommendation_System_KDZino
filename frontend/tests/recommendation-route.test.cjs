const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");
const { webcrypto } = require("node:crypto");
const ts = require("typescript");

const compiled = ts.transpileModule(readFileSync(path.join(__dirname,
  "../src/app/api/recommendations/route.ts"), "utf8"), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
}).outputText;

function route(fetch, fetchRecommendations = async () => { throw Error("offline"); }) {
  const exports = {};
  vm.runInNewContext(compiled, {
    exports, fetch, URL, Response, AbortSignal, crypto: webcrypto, process: { env: {} },
    require: () => ({ fetchRecommendations }),
  });
  return exports.GET;
}

test("selected product ID reaches FastAPI and changes the resulting feed", async () => {
  const calls = [];
  const get = route(async url => {
    calls.push(new URL(url));
    const id = new URL(url).searchParams.get("item_id");
    return Response.json({ algorithm: "content_based_v1", recommendations: [
      { item_id: id, name: "Current item", images: [] },
      { item_id: `${id}-similar`, name: `Related to ${id}`, images: [] },
    ] });
  });
  const first = await (await get(new Request("http://local/api/recommendations?context=product_detail&trigger_item_id=books"))).json();
  const second = await (await get(new Request("http://local/api/recommendations?context=product_detail&trigger_item_id=crafts"))).json();
  assert.equal(calls[0].searchParams.get("item_id"), "books");
  assert.equal(calls[1].searchParams.get("item_id"), "crafts");
  assert.equal(first.model_name, "content_based_v1");
  assert.deepEqual(first.items.map(item => item.id), ["books-similar"]);
  assert.deepEqual(second.items.map(item => item.id), ["crafts-similar"]);
});

test("detail requests without an item fail instead of returning a generic feed", async () => {
  let called = false;
  const get = route(async () => { called = true; });
  for (const suffix of ["", "&trigger_item_id=bad%20id"]) {
    const response = await get(new Request(`http://local/api/recommendations?context=product_detail${suffix}`));
    assert.equal(response.status, 400);
  }
  assert.equal(called, false);
});

test("Python fallback preserves the selected item and exclusion", async () => {
  let input;
  const get = route(async () => { throw Error("backend unavailable"); }, async (...args) => {
    input = args;
    return { trigger_item_id: args[1], items: [{ id: "crafts" }, { id: "related" }] };
  });
  const result = await (await get(new Request("http://local/api/recommendations?context=product_detail&trigger_item_id=crafts"))).json();
  assert.equal(input[1], "crafts");
  assert.deepEqual(result.items.map(item => item.id), ["related"]);
});

test("dependency failure returns a recoverable safe error", async () => {
  const get = route(async () => { throw Error("internal connection details"); });
  const response = await get(new Request("http://local/api/recommendations?context=product_detail&trigger_item_id=crafts"));
  assert.equal(response.status, 503);
  assert.equal((await response.text()).includes("internal connection details"), false);
});

test("home uses authenticated personalized feed and preserves warm status", async () => {
  const get = route(async (url, options) => {
    assert.equal(new URL(url).pathname, "/api/v1/recommendations/feed");
    assert.equal(options.headers.Authorization, "Bearer demo-token");
    return Response.json({ items: [{ id: "a" }], segment: "warm", degraded: true,
      model_status: { als: "ready" }, retrieval_modes: { twotower: "history_item_pool" }, model_name: "hybrid" });
  });
  const data = await (await get(new Request("http://local/api/recommendations?context=home", {
    headers: { Authorization: "Bearer demo-token" },
  }))).json();
  assert.equal(data.segment, "warm");
  assert.equal(data.model_status.als, "ready");
  assert.equal(data.retrieval_modes.twotower, "history_item_pool");
  assert.equal(data.degraded, true);
});

test("failed personal feed never silently substitutes anonymous recommendations", async () => {
  let fallback = false;
  const get = route(async () => { throw Error("offline"); }, async () => { fallback = true; });
  assert.equal((await get(new Request("http://local/api/recommendations?context=home"))).status, 503);
  assert.equal(fallback, false);
});

test("home forwards cursor, preserves anonymous identity and returns pagination metadata", async () => {
  const id = "12345678-1234-4234-8234-123456789abc";
  const get = route(async url => {
    const query = new URL(url).searchParams;
    assert.equal(query.get("cursor"), id + ":12");
    assert.equal(query.get("anonymous_id"), id);
    return Response.json({ request_id: id, items: [{ id: "next", position: 13 }],
      has_more: true, next_cursor: id + ":24", experiment: { id: "test", variant: "A", ranker: "dcn" } });
  });
  const response = await get(new Request("http://local/api/recommendations?context=home&cursor=" + id + ":12", {
    headers: { Cookie: "merrec_experiment_id=" + id },
  }));
  const data = await response.json();
  assert.equal(data.items[0].position, 13);
  assert.equal(data.next_cursor, id + ":24");
  assert.equal(data.experiment.variant, "A");
  assert.ok(response.headers.get("Set-Cookie").includes("HttpOnly"));
});

test("invalid or expired cursors fail safely instead of starting an anonymous feed", async () => {
  let calls = 0;
  const get = route(async () => { calls++; return Response.json({}, { status: 410 }); });
  assert.equal((await get(new Request("http://local/api/recommendations?cursor=bad"))).status, 400);
  assert.equal(calls, 0);
  const response = await get(new Request("http://local/api/recommendations?cursor=12345678-1234-4234-8234-123456789abc:12"));
  assert.equal(response.status, 410);
});

test("failed first feed still pins the anonymous experiment identity for retries", async () => {
  const get = route(async () => { throw Error("offline"); });
  const response = await get(new Request("http://local/api/recommendations?context=home"));
  assert.equal(response.status, 503);
  assert.match(response.headers.get("Set-Cookie"), /^merrec_experiment_id=[0-9a-f-]{36};/);
});
