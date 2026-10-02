"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useCart } from "@/lib/cart";
import { useAuth } from "@/lib/auth-context";
import { formatVND, toVND } from "@/lib/merrecData";
import CartItemRow from "@/components/cart/CartItemRow";
import RecommendationStrip from "@/components/recommendation-strip/RecommendationStrip";
import BenefitsStrip from "@/components/benefits-strip/BenefitsStrip";
import "./cart.css";

export default function CartPage() {
  const router = useRouter();
  const { user } = useAuth();
  const { items: cartItems, update: setCartItems } = useCart();

  const subtotal = cartItems.reduce(
    (sum, item) => sum + toVND(item.product.price, item.product.currency) * item.qty,
    0
  );

  const handleUpdateQty = (id: string, newQty: number) => {
    setCartItems((prev) =>
      prev.map((item) => (item.product.id === id ? { ...item, qty: newQty } : item))
    );
  };

  const handleRemoveItem = (id: string) => {
    setCartItems((prev) => prev.filter((item) => item.product.id !== id));
  };

  return (
    <div className="cart-page-wrapper">
      <div className="container-custom">
        <div className="breadcrumb">
          <Link href="/">Trang chủ</Link> › <span className="current">Giỏ hàng</span>
        </div>

        <div className="cart-header-group">
          <h1 className="cart-title">Giỏ hàng của bạn</h1>
          <div className="cart-title-underline" />
        </div>

        <div className="cart-layout">
          {/* ITEM LIST */}
          <div className="cart-items-card">
            {cartItems.length === 0 ? (
              <div className="cart-empty-box">
                <p className="cart-empty-text">Giỏ hàng của bạn đang trống</p>
              </div>
            ) : (
              cartItems.map(({ product, qty }) => (
                <CartItemRow
                  key={product.id}
                  product={product}
                  qty={qty}
                  onUpdateQty={(newQty) => handleUpdateQty(product.id, newQty)}
                  onRemove={() => handleRemoveItem(product.id)}
                  showQuantityControl={true}
                  showRemoveBtn={true}
                />
              ))
            )}
          </div>

          {/* SUMMARY */}
          {cartItems.length > 0 && (
            <div className="cart-summary-card">
              <h3 className="summary-title">Tóm tắt đơn hàng</h3>

              <div className="summary-row">
                <span>Tạm tính:</span>
                <span>{formatVND(subtotal)}</span>
              </div>

              <div className="summary-row">
                <span>Giảm giá:</span>
                <span style={{ color: "#088751" }}>—</span>
              </div>

              <div className="summary-row">
                <span>Phí vận chuyển:</span>
                <span>Chờ xác nhận</span>
              </div>

              <div className="summary-row total">
                <span>Tổng cộng:</span>
                <span className="total-price">{formatVND(subtotal)}</span>
              </div>

              <Link
                href="/checkout"
                className="checkout-btn"
                onClick={(e) => {
                  e.preventDefault();
                  if (!user) {
                    router.push("/login?redirect=/checkout");
                    return;
                  }
                  router.push("/checkout");
                }}
                style={{ textDecoration: "none" }}
              >
                THANH TOÁN
              </Link>
            </div>
          )}
        </div>

        <RecommendationStrip
          context="cart"
          triggerItemId={cartItems.length > 0 ? cartItems[0].product.id : null}
          excludeItemIds={cartItems.map((item) => item.product.id)}
          title="💡 Có thể bạn cũng thích"
          limit={6}
        />

        <div style={{ marginTop: "40px" }}>
          <BenefitsStrip />
        </div>
      </div>
    </div>
  );
}
