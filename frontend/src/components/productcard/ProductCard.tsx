"use client";

import Link from "next/link";
import { useState } from "react";
import ProductImage from "./ProductImage";
import { addToCart } from "@/lib/cart";
import { formatPrice, Product } from "@/lib/merrecData";
import "./Product.css";

interface ProductCardProps {
  id?: string;
  name?: string;
  price?: string | number;
  image?: string;
  rating?: number;
  product?: Product;
}

export default function ProductCard(props: ProductCardProps) {
  const product = props.product;
  const [liked, setLiked] = useState(false);
  const [notice, setNotice] = useState("");

  const id = product?.id || props.id || "1";
  const name = product?.name || props.name || "Sản phẩm";
  const rawPrice = product?.price ?? props.price ?? 0;
  const priceStr = typeof rawPrice === "number" ? formatPrice(rawPrice, product?.currency) : rawPrice;
  const image = product?.image || props.image || "/products/demo.png";
  const rating = product?.rating ?? props.rating ?? 0;
  const discount = product?.discount || 0;
  const originalPrice = product?.originalPrice;
  const soldCount = product?.soldCount ?? 0;

  if (!image) return null;

  return (
    <div className="product-card">
      {discount > 0 && (
        <span className="badge-discount">-{discount}%</span>
      )}

      <button className="wishlist-btn" title="Yêu thích" aria-label="Yêu thích" aria-pressed={liked} onClick={() => setLiked(!liked)}>
        {liked ? "♥" : "♡"}
      </button>

      <Link href={`/products/${id}`} className="product-image">
        <ProductImage key={id} id={id} name={name} src={product?.source === "merrec" ? undefined : image} />
      </Link>

      <div className="product-info">
        <Link href={`/products/${id}`}>
          <h3 className="product-name" title={name}>
            {name}
          </h3>

          <div className="product-price-row">
            <span className="product-price">{priceStr}</span>
            {originalPrice && originalPrice > (typeof rawPrice === "number" ? rawPrice : 0) && (
              <span className="old-price">{formatPrice(originalPrice, product?.currency)}</span>
            )}
          </div>
        </Link>

        <div className="product-meta-row">
          <div className="product-rating">
            {rating > 0 ? `★ ${rating}` : product?.condition || "Xem chi tiết"} {soldCount > 0 && <span className="sold-count">| Đã bán {soldCount > 1000 ? `${(soldCount / 1000).toFixed(1)}k` : soldCount}</span>}
          </div>
          <button className="add-cart-mini-btn" title="Thêm vào giỏ" aria-label={`Thêm ${name} vào giỏ`} onClick={() => { if (product) { try { addToCart(product, 1); setNotice("Đã thêm vào giỏ"); } catch { setNotice("Chưa thêm được vào giỏ"); } } }}>
            🛒
          </button>
        </div>
        {notice && <small role="status">{notice}</small>}
      </div>
    </div>
  );
}
