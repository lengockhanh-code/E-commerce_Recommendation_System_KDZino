"use client";

import { useState } from "react";
import { useCart } from "@/lib/cart";
import ProductImage from "@/components/productcard/ProductImage";
import Link from "next/link";
import { formatPrice, formatVND, toVND } from "@/lib/merrecData";
import "./cart.css";

export default function CartPage() {
  const { items: cartItems, update: setCartItems } = useCart();
  const [checkoutNotice, setCheckoutNotice] = useState("");

  const subtotal = cartItems.reduce((sum, item) => sum + toVND(item.product.price, item.product.currency) * item.qty, 0);

  const removeItem = (id: string) => {
    setCartItems((prev) => prev.filter((i) => i.product.id !== id));
  };

  return (
    <div className="cart-page-wrapper">
      <div className="container-custom">
        <div className="breadcrumb">
          <Link href="/">Trang chủ</Link> › <span className="current">Giỏ hàng</span>
        </div>

        <h1 className="cart-title">Giỏ hàng của bạn ({cartItems.length} sản phẩm)</h1>

        <div className="cart-layout">
          {/* ITEM LIST */}
          <div className="cart-items-card">
            {cartItems.length === 0 ? (
              <div style={{ textAlign: "center", padding: "40px 0", color: "#666" }}>
                <p style={{ fontSize: "16px", marginBottom: "16px" }}>Giỏ hàng của bạn đang trống</p>
                <Link href="/products" className="checkout-btn" style={{ padding: "10px 24px" }}>
                  Tiếp tục mua sắm
                </Link>
              </div>
            ) : (
              cartItems.map(({ product, qty }) => (
                <div className="cart-item-row" key={product.id}>
                  <div className="cart-item-img">
                    <ProductImage id={product.id} name={product.name} src={product.image || undefined} />
                  </div>

                  <div className="cart-item-details">
                    <span className="cart-item-name">{product.name}</span>
                    <span className="cart-item-price">{formatPrice(product.price, product.currency)}</span>
                  </div>

                  <div className="quantity-control">
                    <button
                      className="qty-btn"
                      onClick={() =>
                        setCartItems((prev) =>
                          prev.map((i) =>
                            i.product.id === product.id ? { ...i, qty: Math.max(1, i.qty - 1) } : i
                          )
                        )
                      }
                    >
                      -
                    </button>
                    <span className="qty-val">{qty}</span>
                    <button
                      className="qty-btn"
                      onClick={() =>
                        setCartItems((prev) =>
                          prev.map((i) =>
                            i.product.id === product.id ? { ...i, qty: Math.min(i.product.stockKnown ? i.product.stockCount : 99, i.qty + 1) } : i
                          )
                        )
                      }
                    >
                      +
                    </button>
                  </div>

                  <button className="cart-item-remove" onClick={() => removeItem(product.id)}>
                    ✕
                  </button>
                </div>
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

              <button className="checkout-btn" onClick={() => setCheckoutNotice("Giỏ hàng đã được lưu. Chức năng thanh toán trực tuyến chưa được kết nối.")}>Tiến hành thanh toán</button>
              <p role="status">{checkoutNotice}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
