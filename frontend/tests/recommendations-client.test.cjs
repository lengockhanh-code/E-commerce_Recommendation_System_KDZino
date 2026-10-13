const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");
const ts = require("typescript");
const { webcrypto } = require("node:crypto");
const compiled = ts.transpileModule(readFileSync(path.join(__dirname, "../src/lib/recommendations-client.ts"), "utf8"), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
}).outputText;
function client(fetch) {
  const data = new Map();
  const storage = { getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, value), removeItem: key => data.delete(key) };
  const exports = {};
  vm.runInNewContext(compiled, { exports, fetch, URL, Response, AbortSignal, crypto: webcrypto,
    localStorage: storage, sessionStorage: { ...storage }, Event,
    window: { location: { origin: "http://local" }, dispatchEvent() {} } });
  storage.setItem("merrec_interactions:guest", JSON.stringify([{ item_id: "a", event_type: "view", event_key: webcrypto.randomUUID(), session_id: webcrypto.randomUUID() }]));
  return { api: exports, storage };
}
test("a hanging event write does not delay loading recommendations", async () => {
  const calls = [];
  const { api, storage } = client(async url => {
    calls.push(String(url));
    if (url === "/api/events") return new Promise(() => {});
    return Response.json({ request_id: "r", items: [{ id: "recommended" }] });
  });
  const result = await api.fetchRecommendationsClient("home");
  assert.equal(result.items[0].id, "recommended");
  assert.ok(calls.some(url => url.includes("/api/recommendations")));
  assert.equal(JSON.parse(storage.getItem("merrec_interactions:guest")).length, 1);
});
test("failed writes remain queued and a later successful retry persists the receipt", async () => {
  let available = false;
  const { api, storage } = client(async url => url === "/api/events"
    ? available ? Response.json({ status: "success", event_id: "1" }) : Response.json({}, { status: 503 })
    : Response.json({ request_id: "r", items: [{ id: "recommended" }] }));
  assert.equal((await api.fetchRecommendationsClient("home")).items.length, 1);
  await api.flushPendingInteractions();
  assert.equal(JSON.parse(storage.getItem("merrec_interactions:guest")).length, 1);
  available = true;
  assert.equal(await api.flushPendingInteractions(), true);
  assert.equal(JSON.parse(storage.getItem("merrec_interactions:guest")).length, 0);
});

test("feed pagination and attributed events keep the original session after inactivity", async () => {
  const calls = [];
  const root = webcrypto.randomUUID();
  const child = webcrypto.randomUUID();
  const { api, storage } = client(async (url, options) => {
    calls.push({ url: String(url), options });
    if (url === "/api/events") return Response.json({ status: "success", event_id: "saved" });
    return Response.json({ request_id: String(url).includes("cursor=") ? child : root,
      next_cursor: `${root}:12`, items: [{ id: "recommended" }] });
  });
  await api.flushPendingInteractions();
  await api.fetchRecommendationsClient("home");
  const first = calls.find(call => call.url.includes("/api/recommendations"));
  const session = first.options.headers["X-Merrec-Session"];
  storage.setItem("merrec_recommendation_session", JSON.stringify({ id: session, userId: "guest", updatedAt: 0 }));
  assert.notEqual(api.recommendationSession(), session);
  await api.fetchRecommendationsClient("home", null, 12, [], { cursor: `${root}:12` });
  assert.equal(calls.filter(call => call.url.includes("/api/recommendations"))[1].options.headers["X-Merrec-Session"], session);
  await api.trackEventClient({ item_id: "recommended", event_type: "impression", recommendation_request_id: child, position: 1 });
  assert.equal(JSON.parse(calls.at(-1).options.body).session_id, session);
});

test("an obsolete cursor offers a fresh feed instead of retrying a forbidden cursor", async () => {
  const { api } = client(async () => Response.json({}, { status: 403 }));
  await assert.rejects(api.fetchRecommendationsClient("home", null, 12, [], { cursor: `${webcrypto.randomUUID()}:12` }), /hết hạn/);
});

test("a rejected old attribution is retained without blocking new valid events", async () => {
  const { api, storage } = client(async (_url, options) => {
    const event = JSON.parse(options.body);
    return event.item_id === "a" ? Response.json({}, { status: 403 })
      : Response.json({ status: "success", event_id: "saved" });
  });
  const queued = JSON.parse(storage.getItem("merrec_interactions:guest"));
  storage.setItem("merrec_interactions:guest", JSON.stringify([...queued,
    { ...queued[0], item_id: "valid", event_key: webcrypto.randomUUID() }]));
  assert.equal(await api.flushPendingInteractions(), false);
  assert.deepEqual(JSON.parse(storage.getItem("merrec_interactions:guest")).map(event => event.item_id), ["a"]);
});

test("a fresh feed recovers once from a session bound to an old guest identity", async () => {
  const sessions = [];
  const { api } = client(async (url, options) => {
    if (url === "/api/events") return Response.json({ status: "success", event_id: "saved" });
    sessions.push(options.headers["X-Merrec-Session"]);
    return sessions.length === 1 ? Response.json({}, { status: 403 })
      : Response.json({ request_id: "fresh", items: [{ id: "recommended" }] });
  });
  assert.equal((await api.fetchRecommendationsClient("home")).items.length, 1);
  assert.equal(sessions.length, 2);
  assert.notEqual(sessions[0], sessions[1]);
});
