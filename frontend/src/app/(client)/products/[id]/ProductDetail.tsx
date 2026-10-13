"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Check, ChevronLeft, ChevronRight, Heart, ImageIcon, LoaderCircle, MessageCircle, MessageSquare, Minus, Plus, RotateCcw, ShoppingCart, Store, X, ZoomIn } from "lucide-react";
import { MERREC_CATEGORIES, formatPrice, type Product } from "@/lib/merrecData";
import { loadProductImages, type ProductImageResult } from "@/lib/product-images";
import { addToCart } from "@/lib/cart";
import { animateFlyToCart } from "@/lib/flyToCart";
import { useAuth } from "@/lib/auth-context";
import RecommendationStrip from "@/components/recommendation-strip/RecommendationStrip";
import { trackEventClient } from "@/lib/recommendations-client";

const conditions: Record<string, string> = { New: "Mới", "Like new": "Như mới", Good: "Tốt", Fair: "Khá", Poor: "Đã qua sử dụng" };

export default function ProductDetail({ product }: { product: Product }) {
  const router = useRouter();
  const { user } = useAuth();
  const initialImages: ProductImageResult[] = (product.images && product.images.length > 0)
    ? product.images.map((url, idx) => ({ url, source: product.source || "merrec", title: product.name, score: 1.0, position: idx }))
    : (product.image ? [{ url: product.image, source: product.source || "merrec", title: product.name, score: 1.0, position: 0 }] : []);

  const [images, setImages] = useState<ProductImageResult[]>(initialImages);
  const [imageState, setImageState] = useState(initialImages.length ? "ready" : "loading");
  const [selected, setSelected] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const [qty, setQty] = useState(1);
  const [liked, setLiked] = useState(false);
  const [message, setMessage] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const viewedId = useRef<string | null>(null);
  const likeKey = `merrec_liked:${user?.id || "guest"}:${product.id}`;
  useEffect(() => { setLiked(localStorage.getItem(likeKey) === "true"); }, [likeKey]);

  function toggleLike() {
    const next = !liked;
    localStorage.setItem(likeKey, String(next));
    setLiked(next);
    void trackEventClient({ item_id: product.id, event_type: next ? "like" : "unlike", source_page: "product_detail" });
  }
  const category = MERREC_CATEGORIES.find((item) => item.c0_name === product.c0_name)?.name || product.c0_name;
  const condition = conditions[product.condition] || product.condition;
  const maxQty = product.stockKnown ? product.stockCount : 99;
  const current = images[selected];

  function removeImage(url: string) {
    setImages((items) => items.filter((item) => item.url !== url));
    setSelected(0);
    setImageState("ready");
  }

  useEffect(() => {
    if (initialImages.length > 0 && attempt === 0) return;
    let cancelled = false;
    loadProductImages(product.id, attempt > 0).then((result) => {
      if (!cancelled) { setImages(result); setImageState(result.length ? "ready" : "empty"); }
    }).catch(() => { if (!cancelled) setImageState("error"); });
    return () => { cancelled = true; };
  }, [product.id, attempt]);

  useEffect(() => {
    if (!product.id) return;
    if (viewedId.current === product.id) return;
    viewedId.current = product.id;
    void trackEventClient({ item_id: product.id, event_type: "view", source_page: "product_detail" });
  }, [product.id]);

  function purchase(buyNow = false, event?: React.MouseEvent<HTMLElement>) {
    try {
      addToCart({ ...product, image: current?.reference ? "" : current?.url || "" }, qty);
      if (!buyNow && event) {
        animateFlyToCart(event.currentTarget, current?.url || product.image);
        void trackEventClient({
          item_id: product.id,
          event_type: "cart",
          source_page: "product_detail",
          metadata: { quantity: qty, price: product.price },
        });
      }
      if (buyNow) {
        void trackEventClient({
          item_id: product.id,
          event_type: "buy_start",
          source_page: "product_detail",
          metadata: { quantity: qty, price: product.price },
        });
        if (!user) {
          router.push("/login?redirect=/checkout");
          return;
        }
        router.push("/checkout");
      }
    } catch (error) {
      console.error(error);
    }
  }

  const details = [
    ["Danh mục", [category, product.c1_name, product.c2_name].filter(Boolean).join(" › ")],
    ...(product.brand ? [["Thương hiệu", product.brand]] : []),
    ...(condition ? [["Tình trạng", condition]] : []),
    ...(product.size ? [["Kích cỡ", product.size]] : []),
    ...(product.color ? [["Màu sắc", product.color]] : []),
    ["Mã sản phẩm", product.id],
    ...(product.shipper === "Seller" || product.shipper === "Buyer" ? [["Phí vận chuyển", product.shipper === "Seller" ? "Người bán chi trả" : "Người mua chi trả"]] : []),
  ];

  return <div className="pdp">
    <div className="container-custom pdp-container">
      <nav className="pdp-breadcrumb" aria-label="Đường dẫn">
        <Link href="/">Trang chủ</Link><ChevronRight size={14} /><Link href="/products">Sản phẩm</Link><ChevronRight size={14} />
        <Link href={`/products?category=${encodeURIComponent(product.c0_name)}`}>{category}</Link><ChevronRight size={14} /><span>{product.name}</span>
      </nav>

      <section className="pdp-hero" aria-label="Thông tin sản phẩm">
        <div className="pdp-gallery">
          <div className="pdp-gallery-layout">
            <div className="pdp-thumbs" aria-label="Ảnh sản phẩm">
              {images.map((image, index) => <button key={image.url} className={selected === index ? "active" : ""} onClick={() => setSelected(index)} aria-label={`Xem ảnh ${index + 1}`} aria-pressed={selected === index}>
                <img src={image.url} alt={`${product.name} — ảnh ${index + 1}`} referrerPolicy="no-referrer" onError={() => removeImage(image.url)} />
              </button>)}
              {imageState === "loading" && [0, 1, 2, 3].map((index) => <div className="pdp-thumb-skeleton" key={index} />)}
            </div>
            <div className="pdp-main-image">
              {current ? <>
                <button className="pdp-image-open" onClick={() => dialog.current?.showModal()} aria-label="Phóng to ảnh sản phẩm">
                  <img src={current.url} alt={product.name} referrerPolicy="no-referrer" onError={() => removeImage(current.url)} />
                  <span className="pdp-zoom"><ZoomIn size={18} /></span>
                </button>
                <span className="pdp-image-count">{selected + 1} / {images.length}</span>
                {current.reference && <span style={{ position: "absolute", top: 12, left: 12, background: "white", padding: "6px 10px", fontSize: 12 }}>Ảnh tham khảo — sản phẩm cùng loại</span>}
              </> : <div className="pdp-image-empty">
                {imageState === "loading" ? <LoaderCircle size={38} className="pdp-spin" /> : <ImageIcon size={54} strokeWidth={1} />}
                <strong>{imageState === "loading" ? "Đang tìm ảnh sản phẩm" : "Chưa tìm được ảnh phù hợp"}</strong>
                <span>{imageState === "loading" ? product.name : "Bạn vẫn có thể xem đầy đủ thông tin bên cạnh."}</span>
                {imageState !== "loading" && <button className="pdp-text-button" onClick={() => { setImageState("loading"); setAttempt((value) => value + 1); }}>Thử tìm lại <RotateCcw size={14} /></button>}
              </div>}
            </div>
          </div>
        </div>

        <div className="pdp-info">
          <div className="pdp-title-row"><h1>{product.name}</h1><button className={`pdp-favorite ${liked ? "is-liked" : ""}`} aria-label={liked ? "Bỏ yêu thích" : "Yêu thích sản phẩm"} aria-pressed={liked} onClick={toggleLike}><Heart size={19} fill={liked ? "currentColor" : "none"} /></button></div>
          {(product.rating > 0 || product.soldCount > 0) && <div className="pdp-social-proof">{product.rating > 0 && <a href="#reviews"><span className="pdp-stars">★★★★★</span> {product.rating}</a>}{product.soldCount > 0 && <span>Đã bán {product.soldCount}</span>}</div>}
          <div className="pdp-price-panel">
            <div><strong>{formatPrice(product.price, product.currency)}</strong>{product.originalPrice > product.price && <><del>{formatPrice(product.originalPrice, product.currency)}</del><b>-{product.discount}%</b></>}</div>
          </div>

          <div className="pdp-fields">
            <dl className="pdp-summary">{details.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
            <div className="pdp-field"><label htmlFor="product-quantity">Số lượng</label><div className="pdp-quantity-row"><div className="pdp-quantity"><button disabled={qty <= 1} aria-label="Giảm số lượng" onClick={() => setQty((value) => Math.max(1, value - 1))}><Minus size={15} /></button><input id="product-quantity" type="number" min={1} max={maxQty} value={qty} onChange={(event) => setQty(Math.min(Math.max(1, Number(event.target.value) || 1), Math.max(1, maxQty)))} /><button disabled={qty >= maxQty} aria-label="Tăng số lượng" onClick={() => setQty((value) => Math.min(maxQty, value + 1))}><Plus size={15} /></button></div>{product.stockKnown && <small>{product.stockCount} sản phẩm có sẵn</small>}</div></div>
          </div>

          <div className="pdp-buy-actions">
            <button className="pdp-add" onClick={(e) => purchase(false, e)} disabled={product.stockKnown && !product.stockCount}>
              <ShoppingCart size={21} />Thêm vào giỏ hàng
            </button>
            <button className="pdp-buy" onClick={(e) => purchase(true, e)} disabled={product.stockKnown && !product.stockCount}>
              Mua ngay<ArrowRight size={18} />
            </button>
          </div>
        </div>
      </section>

      {/* THÔNG TIN NGƯỜI BÁN & CHAT VỚI NGƯỜI BÁN (SELLER CARD - IMAGE 2) */}
      <section className="pdp-seller-box" aria-label="Thông tin người bán">
        <div className="pdp-seller-left">
          <div className="pdp-seller-avatar-wrap">
            <div className="pdp-seller-avatar">
              <span>{product.brand ? product.brand.slice(0, 3).toUpperCase() : "KDZ"}</span>
            </div>
            <span className="pdp-seller-mall-badge">KDZ Mall</span>
          </div>

          <div className="pdp-seller-profile">
            <div className="pdp-seller-name-row">
              <h3>{product.brand ? `${product.brand} Official Store` : "KDZ Fashion Chính Hãng"}</h3>
            </div>
            <div className="pdp-seller-status">
              <span className="status-online-dot"></span> online
            </div>
            <div className="pdp-seller-buttons">
              <button
                type="button"
                className="btn-seller-chat"
                onClick={() => {
                  window.dispatchEvent(
                    new CustomEvent("merrec:open-chat", {
                      detail: { product },
                    })
                  );
                }}
              >
                <MessageSquare size={16} /> Chat Ngay
              </button>
              <button
                type="button"
                className="btn-seller-view"
                onClick={() => router.push(`/products?brand=${encodeURIComponent(product.brand || "KDZ")}`)}
              >
                <Store size={16} /> Xem Shop
              </button>
            </div>
          </div>
        </div>

        <div className="pdp-seller-divider" />

        <div className="pdp-seller-stats">
          <div className="pdp-seller-stat-col">
            <div className="seller-stat-item">
              <span className="stat-name">Đánh Giá</span>
              <span className="stat-val highlight">{product.rating ? `${product.rating}k` : "12.8k"}</span>
            </div>
            <div className="seller-stat-item">
              <span className="stat-name">Sản Phẩm</span>
              <span className="stat-val highlight">{product.stockCount ? `${product.stockCount * 4}` : "156"}</span>
            </div>
          </div>
          <div className="pdp-seller-stat-col">
            <div className="seller-stat-item">
              <span className="stat-name">Tỉ Lệ Phản Hồi</span>
              <span className="stat-val highlight">99%</span>
            </div>
            <div className="seller-stat-item">
              <span className="stat-name">Thời Gian Phản Hồi</span>
              <span className="stat-val highlight">trong vài phút</span>
            </div>
          </div>
          <div className="pdp-seller-stat-col">
            <div className="seller-stat-item">
              <span className="stat-name">Tham Gia</span>
              <span className="stat-val highlight">2 năm trước</span>
            </div>
            <div className="seller-stat-item">
              <span className="stat-name">Người Theo Dõi</span>
              <span className="stat-val highlight">45.2k</span>
            </div>
          </div>
        </div>
      </section>

      <RecommendationStrip
        context="product_detail"
        triggerItemId={product.id}
        title="Sản phẩm tương tự"
        limit={12}
        excludeItemIds={[product.id]}
      />

      <div className="pdp-bottom-layout">
        <div>
          <section className="pdp-section" id="specifications"><div className="pdp-tabs"><a className="active" href="#specifications">Chi tiết sản phẩm</a><a href="#description">Mô tả sản phẩm</a><a href="#reviews">Đánh giá</a></div><h2>CHI TIẾT SẢN PHẨM</h2><dl className="pdp-specs">{details.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
            <div id="description" className="pdp-description"><h2>MÔ TẢ SẢN PHẨM</h2><h3>{product.name}</h3><p style={{ whiteSpace: "pre-line" }}>{product.description?.trim() || "Chưa có mô tả sản phẩm."}</p></div>
          </section>
          <section className="pdp-section" id="reviews"><h2>ĐÁNH GIÁ SẢN PHẨM</h2><div className="pdp-review-empty"><span>☆ ☆ ☆ ☆ ☆</span><strong>Chưa có đánh giá cho sản phẩm này</strong><p>Đánh giá từ người mua sẽ xuất hiện tại đây.</p></div></section>
        </div>
      </div>
    </div>
    <dialog ref={dialog} className="pdp-lightbox" onClick={(event) => { if (event.target === event.currentTarget) dialog.current?.close(); }}><button className="pdp-lightbox-close" onClick={() => dialog.current?.close()} aria-label="Đóng ảnh"><X /></button>{current && <img src={current.url} alt={product.name} referrerPolicy="no-referrer" />}<div><button aria-label="Ảnh trước" disabled={selected === 0} onClick={() => setSelected((value) => value - 1)}><ChevronLeft /></button><span>{selected + 1} / {images.length}</span><button aria-label="Ảnh tiếp theo" disabled={selected === images.length - 1} onClick={() => setSelected((value) => value + 1)}><ChevronRight /></button></div></dialog>
  </div>;
}
