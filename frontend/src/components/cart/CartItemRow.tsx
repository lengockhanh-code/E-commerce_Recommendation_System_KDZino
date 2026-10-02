"use client";

import Link from "next/link";
import ProductImage from "@/components/productcard/ProductImage";
import { formatPrice, formatVND, toVND, type Product } from "@/lib/merrecData";
import "./CartItemRow.css";

export interface CartItemRowProps {
  product: Product;
  qty: number;
  onUpdateQty?: (newQty: number) => void;
  onRemove?: () => void;
  showQuantityControl?: boolean;
  showRemoveBtn?: boolean;
}

export default function CartItemRow({
  product,
  qty,
  onUpdateQty,
  onRemove,
  showQuantityControl = true,
  showRemoveBtn = true,
}: CartItemRowProps) {
  const unitPriceVnd = toVND(product.price, product.currency);
  const lineTotalVnd = unitPriceVnd * qty;
  const maxQty = product.stockKnown ? product.stockCount : 99;

  return (
    <div className="cart-item-row-comp">
      {/* LEFT: PRODUCT IMAGE */}
      <div className="cart-item-thumb-wrapper">
        <ProductImage
          id={product.id}
          name={product.name}
          src={product.image || undefined}
        />
        {product.discount > 0 && (
          <div className="cart-item-badge-offer">
            <span>{formatVND(unitPriceVnd)}</span>
            <span>- {product.discount}%</span>
          </div>
        )}
      </div>

      {/* MIDDLE: TITLE, UNIT PRICE, QUANTITY BOX */}
      <div className="cart-item-info-col">
        <Link href={`/products/${product.id}`} className="cart-item-title-link">
          <h3 className="cart-item-name-text">{product.name}</h3>
        </Link>

        <span className="cart-item-unit-price">
          {formatVND(unitPriceVnd)}
        </span>

        {showQuantityControl && (
          <div className="cart-qty-box">
            <button
              type="button"
              className="cart-qty-btn"
              disabled={qty <= 1}
              onClick={() => onUpdateQty && onUpdateQty(Math.max(1, qty - 1))}
              aria-label="Giảm số lượng"
            >
              -
            </button>
            <div className="cart-qty-val">{qty}</div>
            <button
              type="button"
              className="cart-qty-btn"
              disabled={qty >= maxQty}
              onClick={() => onUpdateQty && onUpdateQty(Math.min(maxQty, qty + 1))}
              aria-label="Tăng số lượng"
            >
              +
            </button>
          </div>
        )}
      </div>

      {/* RIGHT: REMOVE BUTTON & LINE TOTAL */}
      <div className="cart-item-right-col">
        {showRemoveBtn ? (
          <button
            type="button"
            className="cart-item-remove-btn"
            onClick={onRemove}
            title="Xóa sản phẩm"
            aria-label={`Xóa ${product.name} khỏi giỏ hàng`}
          >
            ✕
          </button>
        ) : (
          <div />
        )}

        <div className="cart-item-line-total">
          {formatVND(lineTotalVnd)}
        </div>
      </div>
    </div>
  );
}
