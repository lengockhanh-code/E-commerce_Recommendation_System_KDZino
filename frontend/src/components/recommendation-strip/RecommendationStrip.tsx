"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { LoaderCircle } from "lucide-react";
import ProductCard from "@/components/productcard/ProductCard";
import { type Product } from "@/lib/merrecData";
import { fetchRecommendationsClient, rememberRecommendation, trackEventClient } from "@/lib/recommendations-client";
import { useAuth } from "@/lib/auth-context";
import "./RecommendationStrip.css";

interface RecommendationStripProps {
  title?: string;
  context: "home" | "product_detail" | "cart";
  triggerItemId?: string | null;
  excludeItemIds?: string[];
  limit?: number;
  className?: string;
}
interface FeedCard { product: Product; requestId: string; position: number }

export default function RecommendationStrip({ title = "Gợi ý dành riêng cho bạn", context,
  triggerItemId = null, excludeItemIds = [], limit = 12, className = "" }: RecommendationStripProps) {
  const { user, isLoading: authLoading } = useAuth();
  const [cards, setCards] = useState<FeedCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [displayLimit, setDisplayLimit] = useState(limit);
  const cursor = useRef<string | null>(null);
  const busy = useRef(false);
  const generation = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const sentinel = useRef<HTMLDivElement>(null);
  const grid = useRef<HTMLDivElement>(null);
  const impressions = useRef(new Set<string>());
  const cardsRef = useRef<FeedCard[]>([]);
  const lastLoadScroll = useRef(0);
  const excludeKey = excludeItemIds.join(",");
  const home = context === "home";

  const load = useCallback(async (append: boolean) => {
    if (busy.current || authLoading) return;
    busy.current = true;
    const current = generation.current;
    const previousCursor = append ? cursor.current : null;
    const abort = new AbortController();
    controller.current = abort;
    const startedAt = performance.now();
    if (append) setLoadingMore(true); else { setLoading(true); setCards([]); cardsRef.current = []; }
    setError(null);
    try {
      const data = await fetchRecommendationsClient(context, triggerItemId, home ? limit : displayLimit,
        excludeKey ? excludeKey.split(",") : [], { cursor: previousCursor, signal: abort.signal });
      // Keep the progress indicator perceptible even for cached feed pages.
      if (append) await new Promise<void>((resolve) => window.setTimeout(resolve, Math.max(0, 450 - (performance.now() - startedAt))));
      if (current !== generation.current || abort.signal.aborted) return;
      if (append && data.has_more && data.next_cursor === previousCursor) throw new Error("Chưa tải được gợi ý tiếp theo. Vui lòng thử lại.");
      const seen = new Set(append ? cardsRef.current.map((card) => card.product.id) : []);
      const incoming = data.items.filter((product) => {
        if (seen.has(product.id)) return false;
        seen.add(product.id); return true;
      }).map((product, index) => ({ product, requestId: data.request_id, position: product.position ?? index + 1 }));
      cardsRef.current = append ? [...cardsRef.current, ...incoming] : incoming;
      setCards(cardsRef.current);
      lastLoadScroll.current = window.scrollY;
      cursor.current = data.next_cursor ?? null;
      setHasMore(home ? Boolean(data.has_more && data.next_cursor) : incoming.length >= displayLimit && displayLimit < 36);
    } catch (failure) {
      if (current === generation.current && !abort.signal.aborted) {
        setError(failure instanceof Error ? failure.message : "Chưa tải được gợi ý. Vui lòng thử lại.");
      }
    } finally {
      if (current === generation.current) { busy.current = false; setLoading(false); setLoadingMore(false); }
    }
  }, [authLoading, context, displayLimit, excludeKey, home, limit, triggerItemId]);

  useEffect(() => {
    generation.current += 1;
    busy.current = false;
    cursor.current = null;
    lastLoadScroll.current = window.scrollY;
    impressions.current.clear();
    const timer = window.setTimeout(() => { void load(false); }, 0);
    return () => { window.clearTimeout(timer); generation.current += 1; controller.current?.abort(); busy.current = false; };
  }, [load, attempt, user?.id]);

  useEffect(() => {
    const refresh = () => setAttempt((value) => value + 1);
    window.addEventListener("merrec:preferences-changed", refresh);
    if (!home) window.addEventListener("merrec:interaction-saved", refresh);
    return () => { window.removeEventListener("merrec:preferences-changed", refresh); window.removeEventListener("merrec:interaction-saved", refresh); };
  }, [home]);

  useEffect(() => {
    const node = sentinel.current;
    if (!home || !node || !hasMore || loading || loadingMore || error) return;
    const loadAtBottom = () => {
      const bounds = node.getBoundingClientRect();
      if (window.scrollY > lastLoadScroll.current + 8 && bounds.top < window.innerHeight && bounds.bottom > 0) {
        lastLoadScroll.current = window.scrollY;
        void load(true);
      }
    };
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) loadAtBottom();
    }, { threshold: 0 });
    observer.observe(node);
    window.addEventListener("scroll", loadAtBottom, { passive: true });
    return () => { observer.disconnect(); window.removeEventListener("scroll", loadAtBottom); };
  }, [home, cards.length, hasMore, loading, loadingMore, error, load]);

  const markImpression = useCallback((card: FeedCard) => {
    if (context !== "home") return;
    const key = card.requestId + ":" + card.product.id;
    rememberRecommendation(card.product.id, card.requestId, card.position);
    if (impressions.current.has(key)) return;
    impressions.current.add(key);
    void trackEventClient({ item_id: card.product.id, event_type: "impression", source_page: context,
      recommendation_request_id: card.requestId, position: card.position });
  }, [context]);

  useEffect(() => {
    if (!home || !grid.current) return;
    const timers = new Map<Element, ReturnType<typeof setTimeout>>();
    const visible = new Set<Element>();
    const schedule = (target: Element) => {
      if (timers.has(target)) return;
      timers.set(target, setTimeout(() => {
        timers.delete(target);
        const card = cardsRef.current[Number((target as HTMLElement).dataset.recIndex)];
        if (card && visible.has(target) && document.visibilityState === "visible") markImpression(card);
      }, 1000));
    };
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting && entry.intersectionRatio >= .5) { visible.add(entry.target); schedule(entry.target); }
        else { visible.delete(entry.target); const timer = timers.get(entry.target); if (timer) clearTimeout(timer); timers.delete(entry.target); }
      }
    }, { threshold: .5 });
    grid.current.querySelectorAll("[data-rec-index]").forEach((node) => observer.observe(node));
    const visibility = () => {
      timers.forEach(clearTimeout); timers.clear();
      if (document.visibilityState === "visible") visible.forEach(schedule);
    };
    document.addEventListener("visibilitychange", visibility);
    return () => { observer.disconnect(); timers.forEach(clearTimeout); document.removeEventListener("visibilitychange", visibility); };
  }, [cards, home, markImpression]);

  const retry = () => {
    if (error?.includes("hết hạn")) setAttempt((value) => value + 1);
    else void load(cards.length > 0 && home);
  };

  return <section className={"recommendation-strip-section " + className} aria-busy={loading || loadingMore}>
    <div className="rec-section-header"><div className="rec-title-group">
      <h2 className="rec-main-title">{title}</h2>
      {home && user && <Link href="/onboarding">Điều chỉnh sở thích</Link>}
    </div></div>
    {loading && cards.length === 0 && <div className="products-grid-6" aria-label="Đang tải gợi ý">
      {Array.from({ length: Math.min(limit, 12) }, (_, index) => <div key={index} className="rec-card-skeleton" />)}
    </div>}
    {cards.length > 0 && <div className="products-grid-6" ref={grid}>
      {cards.map((card, index) => <div key={card.requestId + ":" + card.product.id} data-rec-index={index}
        onClick={(event) => {
          if (!(event.target as Element).closest("a")) return;
          markImpression(card);
          void trackEventClient({ item_id: card.product.id, event_type: "click", source_page: context,
            ...(home ? { recommendation_request_id: card.requestId, position: card.position } : {}) });
        }}><ProductCard product={card.product} /></div>)}
    </div>}
    {error && <div className="rec-error-state" role="alert"><p>{error}</p>
      <button type="button" className="rec-retry-btn" onClick={retry}>{error.includes("hết hạn") ? "Tải lại gợi ý" : "Thử lại"}</button>
    </div>}
    {!loading && !error && cards.length === 0 && <div className="rec-empty-state">Chưa có sản phẩm gợi ý phù hợp.</div>}
    {home && hasMore && <div ref={sentinel} className="rec-load-sentinel">
      {loadingMore && <div className="rec-loading-more" role="status" aria-label="Đang tải gợi ý"><LoaderCircle size={24} className="rec-spinner" aria-hidden="true" /></div>}
    </div>}
    {!home && hasMore && !loading && !error && <button type="button" className="rec-retry-btn" onClick={() => setDisplayLimit((value) => Math.min(value + 12, 36))}>Xem thêm sản phẩm</button>}
    {home && cards.length > 0 && !hasMore && !loading && !error && <p className="rec-feed-end">Chưa có thêm sản phẩm gợi ý phù hợp.</p>}
  </section>;
}
