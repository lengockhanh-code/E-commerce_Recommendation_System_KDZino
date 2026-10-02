"use client";

import { useEffect, useState } from "react";
import ProductCard from "@/components/productcard/ProductCard";
import { type Product } from "@/lib/merrecData";
import { fetchRecommendationsClient, trackEventClient } from "@/lib/recommendations-client";
import "./RecommendationStrip.css";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

interface RecommendationStripProps {
  title?: string;
  context: "home" | "product_detail" | "cart";
  triggerItemId?: string | null;
  excludeItemIds?: string[];
  limit?: number;
  className?: string;
}

export default function RecommendationStrip({
  title = "✨ Gợi ý dành riêng cho bạn",
  context,
  triggerItemId = null,
  excludeItemIds = [],
  limit = 12,
  className = "",
}: RecommendationStripProps) {
  const { user, isLoading: authLoading } = useAuth();
  const [items, setItems] = useState<(Product & { score?: number })[]>([]);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [modelName, setModelName] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [currentLimit, setCurrentLimit] = useState(limit);
  const [degraded, setDegraded] = useState(false);
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const refresh = () => { clearTimeout(timer); timer = setTimeout(() => setAttempt((value) => value + 1), 500); };
    window.addEventListener("merrec:preferences-changed", refresh);
    window.addEventListener("merrec:interaction-saved", refresh);
    return () => { clearTimeout(timer); window.removeEventListener("merrec:preferences-changed", refresh); window.removeEventListener("merrec:interaction-saved", refresh); };
  }, []);

  const excludeKey = excludeItemIds.join(",");

  // Reset states when context or triggerItemId or excludeKey changes
  useEffect(() => {
    setItems([]);
    setCurrentLimit(limit);
    setLoading(true);
    setError(null);
  }, [context, triggerItemId, excludeKey, limit, user?.id]);

  useEffect(() => {
    if (authLoading) return;
    let active = true;

    fetchRecommendationsClient(context, triggerItemId, currentLimit, excludeItemIds)
      .then((data) => {
        if (!active) return;
        const filteredItems = excludeItemIds.length > 0
          ? (data.items || []).filter((it) => !excludeItemIds.includes(it.id))
          : data.items || [];
        setItems(filteredItems);
        setRequestId(data.request_id);
        setModelName(data.model_name);
        setDegraded(Boolean(data.degraded));
        setError(null);
        setLoading(false);
        setLoadingMore(false);
      })
      .catch((err) => {
        if (!active) return;
        setItems([]);
        setError(err instanceof Error && err.message.includes("Tương tác chưa được lưu")
          ? err.message : "Chưa tải được danh sách gợi ý. Vui lòng thử lại.");
        setLoading(false);
        setLoadingMore(false);
      });

    return () => {
      active = false;
    };
  }, [context, triggerItemId, excludeKey, currentLimit, attempt, user?.id, authLoading]);

  const handleProductClick = (product: Product, position: number) => {
    trackEventClient({
      item_id: product.id,
      event_type: "click",
      source_page: context,
      recommendation_request_id: requestId || undefined,
      position: position + 1,
    });
  };

  const handleRetry = () => {
    setLoading(true);
    setError(null);
    setAttempt((prev) => prev + 1);
  };

  const handleLoadMore = () => {
    setLoadingMore(true);
    setCurrentLimit((prev) => prev + 12);
  };

  return (
    <section className={`recommendation-strip-section ${className}`}>
      <div className="rec-section-header">
        <div className="rec-title-group">
          <h2 className="rec-main-title">{title}</h2>
          {context === "home" && user && <Link href="/onboarding">Điều chỉnh sở thích</Link>}
          {modelName && <p className="rec-model-status" role="status">
            Xếp hạng: {modelName.endsWith("/dcn") ? "DCN" : "tín hiệu sản phẩm và tương tác"}
          </p>}
          {degraded && <p role="status">Một phần gợi ý nâng cao tạm thời chưa khả dụng. Đang dùng các tín hiệu hiện có.</p>}
        </div>
      </div>

      {loading && items.length === 0 && (
        <div className="products-grid-6">
          {Array.from({ length: Math.min(currentLimit, 12) }).map((_, idx) => (
            <div key={idx} className="rec-card-skeleton" />
          ))}
        </div>
      )}

      {!loading && error && items.length === 0 && (
        <div className="rec-error-state" role="alert">
          <p>{error}</p>
          <button className="rec-retry-btn" onClick={handleRetry}>
            Thử lại
          </button>
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="rec-empty-state">
          <p>Chưa có sản phẩm gợi ý phù hợp cho mục này.</p>
        </div>
      )}

      {items.length > 0 && (
        <>
          <div className="products-grid-6">
            {items.map((product, index) => (
              <div
                key={`${requestId || "rec"}-${product.id}-${index}`}
                onClick={() => handleProductClick(product, index)}
              >
                <ProductCard product={product} />
              </div>
            ))}
            {loadingMore &&
              Array.from({ length: 6 }).map((_, idx) => (
                <div key={`more-skel-${idx}`} className="rec-card-skeleton" />
              ))}
          </div>

          {currentLimit < 36 && items.length >= currentLimit && (
            <div style={{ textAlign: "center", marginTop: "20px" }}>
              <button
                type="button"
                className="rec-retry-btn"
                style={{
                  background: loadingMore ? "#f5f5f5" : "#f0f8f3",
                  color: loadingMore ? "#888888" : "#008751",
                  border: loadingMore ? "1px solid #cccccc" : "1px solid #008751",
                  padding: "10px 24px",
                  borderRadius: "8px",
                  fontWeight: 600,
                  cursor: loadingMore ? "not-allowed" : "pointer",
                }}
                onClick={handleLoadMore}
                disabled={loadingMore}
              >
                {loadingMore ? "⏳ Đang tải thêm sản phẩm..." : "Xem thêm sản phẩm gợi ý ↓"}
              </button>
            </div>
          )}
        </>
      )}
    </section>
  );
}
