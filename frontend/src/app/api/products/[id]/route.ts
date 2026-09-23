import { getProduct } from "@/lib/catalog-server";
export const runtime = "nodejs";
export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const product = await getProduct((await params).id);
    return Response.json(product ?? { error: "Không tìm thấy sản phẩm" }, { status: product ? 200 : 404 });
  } catch {
    return Response.json({ error: "Chưa đọc được catalog. Vui lòng thử lại." }, { status: 503 });
  }
}
