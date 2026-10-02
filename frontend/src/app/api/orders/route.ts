import { createOrder } from "@/lib/catalog-server";

export const runtime = "nodejs";

interface OrderItemInput {
  item_id: string;
  product_name?: string;
  quantity?: number;
  unit_price?: number;
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    if (!body || !Array.isArray(body.items) || body.items.length === 0) {
      return Response.json({ error: "Đơn hàng phải chứa ít nhất 1 sản phẩm" }, { status: 400 });
    }
    const address = body.shipping_address;
    if (!address || typeof address !== "object" ||
        typeof address.receiver !== "string" || address.receiver.trim().length < 2 ||
        typeof address.phone !== "string" || !/^[0-9+ ]{9,15}$/.test(address.phone.trim()) ||
        typeof address.address !== "string" || address.address.trim().length < 5 ||
        typeof address.province !== "string" || address.province.trim().length < 2) {
      return Response.json({ error: "Thông tin nhận hàng không hợp lệ" }, { status: 400 });
    }
    if (body.payment_method !== "cod") {
      return Response.json({ error: "Hiện chỉ hỗ trợ thanh toán khi nhận hàng" }, { status: 422 });
    }
    if (body.items.some((item: OrderItemInput) => typeof item.item_id !== "string" || !item.item_id.trim() ||
        !Number.isInteger(item.quantity) || Number(item.quantity) < 1 ||
        typeof item.unit_price !== "number" || !Number.isFinite(item.unit_price) || item.unit_price < 0)) {
      return Response.json({ error: "Sản phẩm trong đơn hàng không hợp lệ" }, { status: 400 });
    }

    const res = await createOrder({
      user_id: typeof body.user_id === "string" ? body.user_id : undefined,
      total_amount: body.items.reduce((sum: number, item: OrderItemInput) => sum + (item.unit_price || 0) * (item.quantity || 0), 0) + 3000,
      shipping_address: { receiver: address.receiver.trim(), phone: address.phone.trim(), address: address.address.trim(), province: address.province.trim() },
      payment_method: "cod",
      items: body.items.map((item: OrderItemInput) => ({
        item_id: String(item.item_id),
        product_name: String(item.product_name || ""),
        quantity: item.quantity!,
        unit_price: item.unit_price!,
      })),
    });

    if (res.status !== "created" || !res.order_id || res.order_id.startsWith("local-")) {
      return Response.json({ error: "Dịch vụ đơn hàng chưa khả dụng. Vui lòng thử lại." }, { status: 503 });
    }
    return Response.json(res, { status: 201, headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ error: "Không thể tạo đơn hàng. Vui lòng thử lại." }, { status: 500 });
  }
}
