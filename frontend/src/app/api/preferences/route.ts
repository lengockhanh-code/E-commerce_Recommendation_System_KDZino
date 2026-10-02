export const runtime = "nodejs";
const API_BASE = process.env.BACKEND_API_URL || "http://localhost:8000/api/v1";

async function proxy(request: Request) {
  const authorization = request.headers.get("authorization");
  if (!authorization) return Response.json({ error: "Vui lòng đăng nhập" }, { status: 401 });
  try {
    const body = request.method === "PUT" ? await request.json() : undefined;
    const response = await fetch(`${API_BASE}/profile/preferences`, {
      method: request.method,
      headers: { Authorization: authorization, "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify({ categories: body.categories }),
      cache: "no-store",
      signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) return Response.json({ error: response.status === 422
      ? "Chọn tối đa 3 danh mục hợp lệ, không trùng lặp."
      : response.status === 401 ? "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."
      : "Chưa thể lưu hoặc đọc sở thích. Vui lòng thử lại." }, { status: response.status >= 500 ? 503 : response.status });
    return Response.json(await response.json(), { headers: { "Cache-Control": "private, no-store" } });
  } catch {
    return Response.json({ error: "Không thể kết nối dịch vụ sở thích. Vui lòng thử lại." }, { status: 503 });
  }
}

export const GET = proxy;
export const PUT = proxy;
