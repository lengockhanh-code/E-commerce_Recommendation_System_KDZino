export const runtime = "nodejs";
const API_BASE = process.env.BACKEND_API_URL || "http://localhost:8000/api/v1";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const context = searchParams.get("context") || "home";
    const triggerItemId = searchParams.get("trigger_item_id") || null;
    const limit = Number(searchParams.get("limit") || "12");
    if (!Number.isInteger(limit) || limit < 1 || limit > 50 || !["home", "product_detail", "cart"].includes(context)) {
      return Response.json({ error: "Tham số gợi ý không hợp lệ", items: [] }, { status: 400 });
    }
    const excludeParam = searchParams.get("exclude_item_ids");
    const excludeIds = excludeParam
      ? excludeParam.split(",").map((s) => s.trim()).filter(Boolean)
      : [];

    const url = new URL(`${API_BASE}/recommendations/feed`);
    url.searchParams.set("context", context);
    url.searchParams.set("limit", String(limit));
    if (triggerItemId) url.searchParams.set("item_id", triggerItemId);
    if (excludeIds.length) url.searchParams.set("exclude", excludeIds.slice(0, 100).join(","));
    const session = request.headers.get("x-merrec-session");
    if (session) url.searchParams.set("session_id", session);
    const authorization = request.headers.get("authorization");
    const response = await fetch(url, {
      headers: authorization ? { Authorization: authorization } : {},
      cache: "no-store", signal: AbortSignal.timeout(45000),
    });
    if (!response.ok) return Response.json({ error: "Chưa thể tải gợi ý. Vui lòng thử lại.", items: [] }, { status: response.status >= 500 ? 503 : response.status });
    const result = await response.json();

    return Response.json(result, {
      headers: { "Cache-Control": "private, no-store", Vary: "Authorization, X-Merrec-Session" },
    });
  } catch {
    return Response.json(
      { error: "Không thể lấy gợi ý lúc này. Vui lòng thử lại.", items: [] },
      { status: 503 }
    );
  }
}
