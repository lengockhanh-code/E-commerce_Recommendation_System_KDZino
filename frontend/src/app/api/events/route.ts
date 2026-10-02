export const runtime = "nodejs";

const API_BASE = process.env.BACKEND_API_URL || "http://localhost:8000/api/v1";
const VALID_EVENT_TYPES = new Set(["view", "click", "like", "unlike", "cart", "offer", "buy_start", "buy_comp", "view_item", "add_to_cart", "purchase"]);

export async function POST(request: Request) {
  try {
    const authHeader = request.headers.get("Authorization");
    const body = await request.json();
    if (!body || typeof body.item_id !== "string" || !body.item_id.trim()) {
      return Response.json({ error: "item_id không hợp lệ" }, { status: 400 });
    }
    if (!VALID_EVENT_TYPES.has(body.event_type)) {
      return Response.json({ error: "event_type không hợp lệ" }, { status: 400 });
    }

    // Attempt direct FastAPI event logging with user token
    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (authHeader) headers["Authorization"] = authHeader;

      const fastApiRes = await fetch(`${API_BASE}/events`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          item_id: body.item_id.trim(),
          event_type: body.event_type,
          session_id: typeof body.session_id === "string" ? body.session_id : undefined,
          event_key: typeof body.event_key === "string" ? body.event_key : undefined,
          source_page: typeof body.source_page === "string" ? body.source_page : undefined,
          recommendation_request_id: typeof body.recommendation_request_id === "string" ? body.recommendation_request_id : undefined,
          position: typeof body.position === "number" ? body.position : undefined,
          extra_data: body.metadata || body.extra_data || {}
        }),
        signal: AbortSignal.timeout(8000),
      });

      if (fastApiRes.ok) {
        return Response.json(await fastApiRes.json());
      }
      return Response.json({ error: "Chưa thể lưu tương tác" }, { status: fastApiRes.status >= 500 ? 503 : fastApiRes.status });
    } catch {
      return Response.json({ error: "Dịch vụ tương tác tạm thời không khả dụng" }, { status: 503 });
    }
  } catch {
    return Response.json({ error: "Không thể lưu tương tác" }, { status: 500 });
  }
}
