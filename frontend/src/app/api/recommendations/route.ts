import { fetchRecommendations } from "@/lib/catalog-server";

export const runtime = "nodejs";
const API_BASE = process.env.BACKEND_API_URL || "http://localhost:8000/api/v1";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const context = (searchParams.get("context") || "home") as "home" | "product_detail" | "cart";
  const triggerItemId = searchParams.get("trigger_item_id")?.trim() || null;
  const limit = Number(searchParams.get("limit") || "12");
  const cursor = searchParams.get("cursor");

  if (!Number.isInteger(limit) || limit < 1 || limit > 50 || !["home", "product_detail", "cart"].includes(context)
    || (context === "product_detail" && !triggerItemId)
    || (triggerItemId !== null && (triggerItemId.length > 100 || /\s/.test(triggerItemId)))
    || (cursor !== null && (context !== "home" || !/^[0-9a-f-]{36}:\d{1,10}$/i.test(cursor)))) {
    return Response.json({ error: "Tham số gợi ý không hợp lệ", items: [] }, { status: 400 });
  }

  const excludeParam = searchParams.get("exclude_item_ids");
  const excludeIds = excludeParam
    ? excludeParam.split(",").map((s) => s.trim()).filter(Boolean)
    : [];
  if (triggerItemId && !excludeIds.includes(triggerItemId)) excludeIds.push(triggerItemId);

  const session = request.headers.get("x-merrec-session");
  const authorization = request.headers.get("authorization");
  const storedAnonymousId = request.headers.get("cookie")?.match(/(?:^|;\s*)merrec_experiment_id=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:;|$)/i)?.[1];
  const anonymousId = storedAnonymousId || crypto.randomUUID();
  const responseHeaders = { "Cache-Control": "private, no-store", Vary: "Authorization, X-Merrec-Session, Cookie",
    ...(context === "home" ? { "Set-Cookie": `merrec_experiment_id=${anonymousId}; Path=/; HttpOnly; SameSite=Lax; Max-Age=31536000${new URL(request.url).protocol === "https:" ? "; Secure" : ""}` } : {}) };

  try {
    const url = new URL(`${API_BASE}/recommendations${context === "home" ? "/feed" : ""}`);
    url.searchParams.set("context", context);
    url.searchParams.set("limit", String(limit));
    // The FastAPI endpoint names this field item_id. Keeping the browser-facing
    // trigger_item_id separate avoids leaking that backend detail into the UI.
    if (triggerItemId) url.searchParams.set("item_id", triggerItemId);
    if (excludeIds.length) url.searchParams.set("exclude", excludeIds.slice(0, 100).join(","));
    if (session) url.searchParams.set("session_id", session);
    if (context === "home") {
      url.searchParams.set("anonymous_id", anonymousId);
      if (cursor) url.searchParams.set("cursor", cursor);
    }

    const response = await fetch(url, {
      headers: authorization ? { Authorization: authorization } : {},
      cache: "no-store",
      signal: AbortSignal.timeout(context === "home" ? 43000 : 5000),
    });

    if (response.ok) {
      const result = await response.json();
      const rawItems: Record<string, unknown>[] = Array.isArray(result.items)
        ? result.items
        : Array.isArray(result.recommendations)
        ? result.recommendations
        : [];

      const normalizedItems = rawItems
        .map((it) => ({
          ...it,
          id: String(it.id || it.item_id || ""),
        }))
        .filter((it) => it.id && (!excludeIds.length || !excludeIds.includes(it.id)));

      return Response.json({
        request_id: result.request_id || crypto.randomUUID(),
        context: result.context || context,
        trigger_item_id: result.trigger_item_id || triggerItemId,
        model_name: result.model_name || result.algorithm || "recommendations_v1",
        segment: result.segment,
        degraded: result.degraded,
        model_status: result.model_status,
        retrieval_modes: result.retrieval_modes,
        next_cursor: result.next_cursor ?? null,
        has_more: Boolean(result.has_more),
        experiment: result.experiment,
        items: normalizedItems,
      }, {
        headers: responseHeaders,
      });
    }
    if (context === "home") {
      return Response.json({ error: response.status === 410 ? "Danh sách đã hết hạn. Vui lòng tải lại gợi ý." : "Chưa thể tải gợi ý. Vui lòng thử lại.", items: [] }, { status: response.status >= 500 ? 503 : response.status, headers: responseHeaders });
    }
  } catch {
    // Backend service not reachable or timed out -> Fall back to catalog-server
  }

  if (context === "home") {
    return Response.json({ error: "Chưa thể tải gợi ý cá nhân. Vui lòng thử lại.", items: [] }, { status: 503, headers: responseHeaders });
  }

  try {
    const localRes = await fetchRecommendations(context, triggerItemId, limit, session, null);
    if (excludeIds.length > 0 && Array.isArray(localRes.items)) {
      localRes.items = localRes.items.filter((item) => !excludeIds.includes(item.id));
    }
    return Response.json(localRes, {
      headers: { "Cache-Control": "private, no-store" },
    });
  } catch {
    return Response.json(
      { error: "Không thể lấy gợi ý lúc này. Vui lòng thử lại.", items: [] },
      { status: 503 }
    );
  }
}
