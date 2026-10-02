import { findImages, getProduct } from "@/lib/catalog-server";
export const runtime = "nodejs";
export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const product = await getProduct((await params).id);
    if (!product) return Response.json({ error: "Không tìm thấy sản phẩm" }, { status: 404 });
    const images = await findImages(product);
    return Response.json({ images }, { headers: { "Cache-Control": "public, max-age=3600, s-maxage=86400, stale-while-revalidate=86400" } });
  } catch {
    return Response.json({ error: "Dịch vụ tìm ảnh đang bận. Bạn có thể thử lại.", images: [] }, { status: 503 });
  }
}
