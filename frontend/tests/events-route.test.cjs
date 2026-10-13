const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");
const ts = require("typescript");
const compiled = ts.transpileModule(readFileSync(path.join(__dirname, "../src/app/api/events/route.ts"), "utf8"), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
}).outputText;
function route(fetch) {
  const exports = {};
  vm.runInNewContext(compiled, { exports, fetch, Response, AbortSignal, process: { env: {} } });
  return exports.POST;
}
function request(event_type = "impression") {
  return new Request("http://local/api/events", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ item_id: "a", event_type, recommendation_request_id: "r", position: 13 }) });
}
test("impressions are forwarded with request and global position", async () => {
  const post = route(async (_url, options) => {
    const data = JSON.parse(options.body);
    assert.equal(data.event_type, "impression"); assert.equal(data.position, 13);
    assert.equal(data.recommendation_request_id, "r");
    return Response.json({ status: "success", event_id: "1" });
  });
  assert.equal((await post(request())).status, 200);
});
test("dependency failure never acknowledges an unpersisted event", async () => {
  const response = await route(async () => { throw Error("private details"); })(request());
  assert.equal(response.status, 503);
  assert.ok(!(await response.text()).includes("acknowledged"));
});
test("backend ownership failure is preserved rather than bypassed by fallback", async () => {
  assert.equal((await route(async () => Response.json({}, { status: 403 }))(request())).status, 403);
});
