"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCart } from "@/lib/cart";
import { useAuth } from "@/lib/auth-context";
import { formatVND, toVND } from "@/lib/merrecData";
import CartItemRow from "@/components/cart/CartItemRow";
import { trackEventClient } from "@/lib/recommendations-client";
import {
  MapPin,
  Store,
  Ticket,
  MessageSquare,
  Truck,
  CheckCircle,
  CreditCard,
  Banknote,
  Wallet,
  FileText,
  Lock,
  ShieldCheck,
  Headphones,
  RotateCcw,
  ChevronRight,
  HelpCircle,
  MessageCircle,
  Phone,
  Check,
} from "lucide-react";
import "./checkout.css";

export default function CheckoutPage() {
  const router = useRouter();
  const { user, token, isLoading } = useAuth();
  const { items: cartItems, update: setCartItems } = useCart();
  const [shippingMethod, setShippingMethod] = useState<"fast" | "pickup">("fast");
  const [paymentMethod, setPaymentMethod] = useState<"cod" | "bank" | "momo" | "zalopay">("cod");
  const [orderSuccess, setOrderSuccess] = useState(false);
  const [placingOrder, setPlacingOrder] = useState(false);
  const [orderError, setOrderError] = useState("");
  const [recipient, setRecipient] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [province, setProvince] = useState("");

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/login?redirect=/checkout");
    }
  }, [user, isLoading, router]);
  useEffect(() => {
    if (user?.full_name) setRecipient((value) => value || user.full_name || "");
    if (token) {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      fetch(`${apiBase}/profile/addresses`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((res) => (res.ok ? res.json() : []))
        .then((addresses) => {
          if (Array.isArray(addresses) && addresses.length > 0) {
            const def = addresses.find((a: any) => a.is_default) || addresses[0];
            if (def) {
              setPhone((prev) => prev || def.phone || "");
              setAddress((prev) => prev || def.address_line || "");
              setProvince((prev) => prev || def.city || "");
            }
          }
        })
        .catch(() => {});
    }
  }, [user, token]);

  const hasCartItems = cartItems.length > 0;
  const subtotal = cartItems.reduce((sum, item) => sum + toVND(item.product.price, item.product.currency) * item.qty, 0);

  const shippingFee = hasCartItems ? 3000 : 0;
  const total = subtotal + shippingFee;
  const savings = 29800;

  const handlePlaceOrder = async () => {
    if (placingOrder) return;
    setOrderError("");
    if (!hasCartItems) { setOrderError("Giỏ hàng trống. Vui lòng chọn sản phẩm trước khi đặt."); return; }
    if (recipient.trim().length < 2 || !/^[0-9+ ]{9,15}$/.test(phone.trim()) || address.trim().length < 5 || province.trim().length < 2) {
      setOrderError("Vui lòng nhập họ tên, số điện thoại, địa chỉ và tỉnh/thành hợp lệ.");
      return;
    }
    if (paymentMethod !== "cod") { setOrderError("Hiện chỉ hỗ trợ thanh toán khi nhận hàng."); return; }
    setPlacingOrder(true);
    const orderItems = cartItems.map((item) => ({
          item_id: item.product.id,
          product_name: item.product.name,
          quantity: item.qty,
          unit_price: toVND(item.product.price, item.product.currency),
        }));

    try {
      const response = await fetch("/api/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: user?.id,
          total_amount: total,
          payment_method: paymentMethod,
          shipping_address: { receiver: recipient.trim(), phone: phone.trim(), address: address.trim(), province: province.trim() },
          items: orderItems,
        }),
        signal: AbortSignal.timeout(15000),
      });
      const result = await response.json();
      if (!response.ok || result.status !== "created" || !result.order_id) {
        throw new Error(result.error || "Chưa thể tạo đơn hàng. Vui lòng thử lại.");
      }

      setOrderSuccess(true);
      setCartItems(() => []);

      for (const item of orderItems) {
        void trackEventClient({
          item_id: item.item_id,
          event_type: "buy_comp",
          source_page: "checkout",
          metadata: { quantity: item.quantity, unit_price: item.unit_price },
        });
      }
    } catch (err) {
      setOrderError(err instanceof Error ? err.message : "Chưa thể tạo đơn hàng. Vui lòng thử lại.");
    } finally {
      setPlacingOrder(false);
    }
  };

  return (
    <div className="checkout-page">
      <div className="checkout-container">
        {/* BREADCRUMB */}
        <div className="checkout-breadcrumb">
          <Link href="/">Trang chủ</Link>
          <ChevronRight size={12} />
          <Link href="/cart">Giỏ hàng</Link>
          <ChevronRight size={12} />
          <span style={{ color: "#111", fontWeight: 500 }}>Thanh toán</span>
        </div>

     

        {/* 2-COLUMN LAYOUT */}
        <div className="checkout-layout">
          {/* MAIN COLUMN */}
          <div className="checkout-main-col">
            {/* ADDRESS CARD */}
            <div className="checkout-card">
              <div className="card-title-row">
                <div className="card-title-left">
                  <span className="card-icon">
                    <MapPin size={20} />
                  </span>
                  <h2>Địa chỉ nhận hàng</h2>
                </div>
                <span>Vui lòng nhập thông tin thật</span>
              </div>

              <div className="address-info" style={{ display: "grid", gap: 8 }}>
                <label htmlFor="checkout-recipient">Họ và tên</label>
                <input id="checkout-recipient" value={recipient} onChange={(event) => setRecipient(event.target.value)} autoComplete="name" required />
                <label htmlFor="checkout-phone">Số điện thoại</label>
                <input id="checkout-phone" value={phone} onChange={(event) => setPhone(event.target.value)} autoComplete="tel" required />
                <label htmlFor="checkout-address">Địa chỉ nhận hàng</label>
                <input id="checkout-address" value={address} onChange={(event) => setAddress(event.target.value)} autoComplete="street-address" required />
                <label htmlFor="checkout-province">Tỉnh/thành</label>
                <input id="checkout-province" value={province} onChange={(event) => setProvince(event.target.value)} autoComplete="address-level1" required />
              </div>
            </div>

            {/* SHOP PRODUCTS CARD */}
            <div className="checkout-card">
              <div className="card-title-left" style={{ marginBottom: "12px" }}>
                <span className="card-icon">
                  <Store size={20} />
                </span>
                <h2>Siêu Thị Cây Thủy Sinh</h2>
              </div>

              {hasCartItems ? (
                cartItems.map(({ product, qty }) => (
                  <CartItemRow
                    key={product.id}
                    product={product}
                    qty={qty}
                    onUpdateQty={(newQty) => {
                      setCartItems((prev) =>
                        prev.map((item) =>
                          item.product.id === product.id ? { ...item, qty: newQty } : item
                        )
                      );
                    }}
                    showQuantityControl={true}
                    showRemoveBtn={false}
                  />
                ))
              ) : (
                <p>Giỏ hàng trống. <Link href="/products">Tiếp tục chọn sản phẩm</Link>.</p>

              )}
            </div>

            {/* SHOP VOUCHER CARD */}
            <div className="checkout-card clickable-card-row">
              <div className="clickable-left">
                <span className="card-icon red">
                  <Ticket size={20} />
                </span>
                <span className="clickable-title">Voucher của Shop</span>
                <span className="clickable-sub">Chọn hoặc nhập mã giảm giá</span>
              </div>
              <div className="clickable-action">
                Chọn voucher <ChevronRight size={16} />
              </div>
            </div>

            {/* MESSAGE TO SHOP CARD */}
            <div className="checkout-card clickable-card-row">
              <div className="clickable-left">
                <span className="card-icon">
                  <MessageSquare size={20} />
                </span>
                <span className="clickable-title">Lời nhắn cho Shop</span>
              </div>
              <div className="clickable-action">
                Để lại lời nhắn (tùy chọn) <ChevronRight size={16} />
              </div>
            </div>

            {/* SHIPPING METHOD CARD */}
            <div className="checkout-card">
              <div className="card-title-left" style={{ marginBottom: "14px" }}>
                <span className="card-icon">
                  <Truck size={20} />
                </span>
                <h2>Phương thức vận chuyển</h2>
              </div>

              <div className="shipping-options">
                {/* OPTION 1: FAST */}
                <div
                  className={`shipping-option-item ${shippingMethod === "fast" ? "selected" : ""}`}
                  onClick={() => setShippingMethod("fast")}
                >
                  <div className="radio-circle">
                    {shippingMethod === "fast" && <div className="radio-circle-inner" />}
                  </div>

                  <div className="shipping-content">
                    <div className="shipping-top-row">
                      <span className="shipping-date-type">27 Thg 9 - 29 Thg 9 Nhanh</span>
                      <div className="shipping-price-badge">
                        <span className="original-price">32.800đ</span>
                        <span className="final-price">3.000đ</span>
                        <span className="badge-save">
                          <Truck size={12} /> Tiết kiệm
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* OPTION 2: PICKUP POINT */}
                <div
                  className={`shipping-option-item ${shippingMethod === "pickup" ? "selected" : ""}`}
                  onClick={() => setShippingMethod("pickup")}
                >
                  <div className="radio-circle">
                    {shippingMethod === "pickup" && <div className="radio-circle-inner" />}
                  </div>

                  <div className="shipping-content">
                    <div className="shipping-top-row">
                      <span className="shipping-date-type">
                        27 Thg 9 - 29 Thg 9 Điểm nhận hàng
                      </span>
                      <div className="shipping-price-badge">
                        <span className="original-price">32.800đ</span>
                        <span className="final-price">3.000đ</span>
                      </div>
                    </div>

                    <div className="shipping-note-row">
                      <span>🎁 Nhận ngay 1.000 Xu KDZino khi chọn lấy hàng chủ động</span>
                      <span style={{ color: "#088751", fontWeight: 600 }}>
                        Chọn điểm nhận hàng ›
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* CO-CHECK BOX */}
              <div className="co-check-box">
                <CheckCircle size={18} color="#088751" />
                <span>
                  <strong>Được đồng kiểm</strong> Bạn có thể kiểm tra sản phẩm khi nhận hàng
                </span>
              </div>
            </div>

            {/* KDZINO VOUCHER CARD */}
            <div className="checkout-card clickable-card-row">
              <div className="clickable-left">
                <span className="card-icon orange">
                  <Ticket size={20} />
                </span>
                <span className="clickable-title">Mã giảm giá KDZino</span>
                <span className="clickable-sub">Chọn mã giảm giá hoặc nhập mã</span>
              </div>
              <div className="clickable-action">
                Chọn/nhập mã <ChevronRight size={16} />
              </div>
            </div>

            {/* PAYMENT METHOD CARD */}
            <div className="checkout-card">
              <div className="card-title-left" style={{ marginBottom: "14px" }}>
                <span className="card-icon">
                  <CreditCard size={20} />
                </span>
                <h2>Phương thức thanh toán</h2>
              </div>

              <div className="payment-grid">
                {/* OPTION 1: COD */}
                <div
                  className={`payment-card ${paymentMethod === "cod" ? "selected" : ""}`}
                  onClick={() => setPaymentMethod("cod")}
                >
                  <div className="radio-circle">
                    {paymentMethod === "cod" && <div className="radio-circle-inner" />}
                  </div>
                  <Banknote size={20} color="#088751" />
                  <div className="payment-card-text">
                    <span className="payment-card-title">Thanh toán</span>
                    <span className="payment-card-sub">khi nhận hàng (COD)</span>
                  </div>
                </div>

                {/* OPTION 2: BANK CARD */}
                <div
                  className={`payment-card ${paymentMethod === "bank" ? "selected" : ""}`}
                  onClick={() => setPaymentMethod("bank")}
                >
                  <div className="radio-circle">
                    {paymentMethod === "bank" && <div className="radio-circle-inner" />}
                  </div>
                  <CreditCard size={20} color="#2563eb" />
                  <div className="payment-card-text">
                    <span className="payment-card-title">Thẻ ngân hàng</span>
                    <span className="payment-card-sub">Visa, Mastercard, JCB</span>
                  </div>
                </div>

                {/* OPTION 3: MOMO */}
                <div
                  className={`payment-card ${paymentMethod === "momo" ? "selected" : ""}`}
                  onClick={() => setPaymentMethod("momo")}
                >
                  <div className="radio-circle">
                    {paymentMethod === "momo" && <div className="radio-circle-inner" />}
                  </div>
                  <Wallet size={20} color="#a21caf" />
                  <div className="payment-card-text">
                    <span className="payment-card-title">MoMo</span>
                    <span className="payment-card-sub">Ví MoMo</span>
                  </div>
                </div>

                {/* OPTION 4: ZALOPAY */}
                <div
                  className={`payment-card ${paymentMethod === "zalopay" ? "selected" : ""}`}
                  onClick={() => setPaymentMethod("zalopay")}
                >
                  <div className="radio-circle">
                    {paymentMethod === "zalopay" && <div className="radio-circle-inner" />}
                  </div>
                  <Wallet size={20} color="#0284c7" />
                  <div className="payment-card-text">
                    <span className="payment-card-title">ZaloPay</span>
                    <span className="payment-card-sub">Ví ZaloPay</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* SIDEBAR COLUMN */}
          <div className="checkout-sidebar-col">
            {/* ORDER SUMMARY CARD */}
            <div className="checkout-card">
              <div className="summary-card-title">
                <FileText size={20} color="#088751" />
                <span>Tóm tắt đơn hàng</span>
              </div>

              <div className="summary-rows">
                <div className="summary-row-item">
                  <span>Tạm tính ({hasCartItems ? cartItems.length : 1} sản phẩm)</span>
                  <span>{formatVND(subtotal)}</span>
                </div>

                <div className="summary-row-item">
                  <span>Phí vận chuyển</span>
                  <span>{formatVND(shippingFee)}</span>
                </div>

                <div className="summary-row-item">
                  <span>Giảm giá vận chuyển</span>
                  <span>-</span>
                </div>

                <div className="summary-row-item">
                  <span>Voucher của Shop</span>
                  <span>-</span>
                </div>

                <div className="summary-row-item">
                  <span>Mã giảm giá KDZino</span>
                  <span>-</span>
                </div>
              </div>

              <div className="summary-total-row">
                <span className="summary-total-label">Tổng cộng</span>
                <span className="summary-total-val">{formatVND(total)}</span>
              </div>

              <div className="summary-save-row">
                <span>Tiết kiệm {formatVND(savings)}</span>
                <HelpCircle size={14} color="#088751" />
              </div>

              {orderError && <p role="alert" style={{ color: "#b42318", marginBottom: 8 }}>{orderError}</p>}
              <button type="button" className="btn-place-order" onClick={handlePlaceOrder} disabled={!hasCartItems || placingOrder}>
                <Lock size={18} /> {placingOrder ? "Đang đặt hàng…" : "Đặt hàng"}
              </button>

              <p className="terms-disclaimer">
                Bằng cách đặt hàng, bạn đồng ý với <Link href="#">Điều khoản dịch vụ</Link> và{" "}
                <Link href="#">Chính sách bảo mật</Link> của KDZino.
              </p>
            </div>

            {/* COMMITMENT CARD */}
            <div className="checkout-card">
              <div className="commitment-title">
                <ShieldCheck size={20} color="#088751" />
                <span>Cam kết từ KDZino</span>
              </div>

              <div className="commitment-list">
                <div className="commitment-item">
                  <ShieldCheck size={18} className="commitment-icon" />
                  <div className="commitment-text">
                    <strong>Sản phẩm chính hãng</strong>
                    <span>Đảm bảo chất lượng, nguồn gốc rõ ràng</span>
                  </div>
                </div>

                <div className="commitment-item">
                  <Truck size={18} className="commitment-icon" />
                  <div className="commitment-text">
                    <strong>Giao hàng toàn quốc</strong>
                    <span>Nhanh chóng, an toàn</span>
                  </div>
                </div>

                <div className="commitment-item">
                  <Headphones size={18} className="commitment-icon" />
                  <div className="commitment-text">
                    <strong>Hỗ trợ 24/7</strong>
                    <span>Tư vấn, giải đáp mọi thắc mắc</span>
                  </div>
                </div>

                <div className="commitment-item">
                  <RotateCcw size={18} className="commitment-icon" />
                  <div className="commitment-text">
                    <strong>Đổi trả dễ dàng</strong>
                    <span>Theo chính sách đổi trả của KDZino</span>
                  </div>
                </div>
              </div>
            </div>

            {/* NEED SUPPORT CARD */}
            <div className="checkout-card">
              <div className="support-title">
                <Headphones size={18} color="#088751" />
                <span>Cần hỗ trợ?</span>
              </div>
              <p className="support-sub">
                Liên hệ đội ngũ KDZino để được hỗ trợ nhanh chóng
              </p>

              <div className="support-btns">
                <button type="button" className="btn-support">
                  <MessageCircle size={15} /> Chat ngay
                </button>
                <button type="button" className="btn-support hotline">
                  <Phone size={15} /> Hotline: 1900 1234
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* SUCCESS MODAL */}
      {orderSuccess && (
        <div className="order-modal-backdrop">
          <div className="order-modal-card">
            <div className="order-modal-icon">
              <Check size={36} />
            </div>
            <h2>Đặt hàng thành công!</h2>
            <p>
              Cảm ơn bạn đã mua sắm tại <strong>KDZino</strong>. Đơn hàng của bạn đã được ghi nhận và đang được xử lý.
            </p>
            <div className="order-modal-btns">
              <Link href="/" className="btn-modal-home">
                Về trang chủ
              </Link>
              <Link href="/profile/history" className="btn-modal-history">
                Xem lịch sử đơn
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
