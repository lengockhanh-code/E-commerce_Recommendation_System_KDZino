"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Check, ChevronLeft, ChevronRight, Heart, ImageIcon, LoaderCircle, Minus, Plus, RotateCcw, ShoppingCart, X, ZoomIn } from "lucide-react";
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
  const [images, setImages] = useState<ProductImageResult[]>([]);
  const [imageState, setImageState] = useState("loading");
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
      addToCart({ ...product, image: current?.url || "" }, qty);
      if (!buyNow && event) {
        animateFlyToCart(event.currentTarget, current?.url || product.image);
      }
      if (buyNow) {
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

          <div className="pdp-buy-actions"><button className="pdp-add" onClick={(e) => purchase(false, e)} disabled={product.stockKnown && !product.stockCount}><ShoppingCart size={21} />Thêm vào giỏ hàng</button><button className="pdp-buy" onClick={(e) => purchase(true, e)} disabled={product.stockKnown && !product.stockCount}>Mua ngay<ArrowRight size={18} /></button></div>
        </div>
      </section>

      <RecommendationStrip
        context="product_detail"
        triggerItemId={product.id}
        title="Sản phẩm tương tự"
        limit={12}
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
