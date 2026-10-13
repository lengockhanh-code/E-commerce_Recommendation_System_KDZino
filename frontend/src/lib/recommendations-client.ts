import { type Product } from "./merrecData";

export interface RecommendationResponse {
  request_id: string;
  session_id?: string;
  context: string;
  trigger_item_id: string | null;
  model_name: string;
  degraded?: boolean;
  segment?: string;
  candidate_count?: number;
  model_status?: Record<string, string>;
  retrieval_modes?: { twotower?: "trained_user_tower" | "trained_history_tower" | "history_item_pool" | null };
  next_cursor?: string | null;
  has_more?: boolean;
  experiment?: { id: string; variant: "A" | "B"; ranker: "dcn" | "lightgbm" } | null;
  items: (Product & { score?: number; position?: number })[];
}

export function recommendationSession(): string {
  const key = "merrec_recommendation_session";
  const account = localStorage.getItem("merrec_token") || "guest";
  // Reset session attribution on login/logout without storing bearer tokens here.
  let userId = account === "guest" ? "guest" : "signed-in";
  try { userId = JSON.parse(localStorage.getItem("merrec_user") || "null")?.id || userId; } catch { /* use a fresh session */ }
  let existing: { id: string; userId: string; updatedAt: number } | null = null;
  try { existing = JSON.parse(sessionStorage.getItem(key) || "null"); } catch { sessionStorage.removeItem(key); }
  if (existing && existing.userId === userId && Date.now() - existing.updatedAt < 30 * 60 * 1000) {
    sessionStorage.setItem(key, JSON.stringify({ ...existing, updatedAt: Date.now() }));
    return existing.id;
  }
  const id = crypto.randomUUID();
  sessionStorage.setItem(key, JSON.stringify({ id, userId, updatedAt: Date.now() }));
  return id;
}

interface PendingInteraction {
  item_id: string;
  event_type: "impression" | "view" | "click" | "like" | "unlike" | "cart" | "offer" | "offer_make" | "buy_start" | "buy_comp";
  source_page?: string;
  recommendation_request_id?: string;
  position?: number;
  metadata?: Record<string, unknown>;
  event_key: string;
  session_id: string;
}

function outboxKey(): string {
  let id = "guest";
  try { id = JSON.parse(localStorage.getItem("merrec_user") || "null")?.id || id; } catch { /* guest */ }
  return `merrec_interactions:${id}`;
}

function requestSession(requestId: string): string | undefined {
  try {
    return JSON.parse(sessionStorage.getItem(`merrec_request_sessions:${outboxKey()}`) || "{}")[requestId];
  } catch { return undefined; }
}

function rememberRequestSession(requestId: string, sessionId: string) {
  const key = `merrec_request_sessions:${outboxKey()}`;
  try {
    const sessions = JSON.parse(sessionStorage.getItem(key) || "{}");
    sessions[requestId] = sessionId;
    sessionStorage.setItem(key, JSON.stringify(sessions));
  } catch { /* Storage may be unavailable. */ }
}

function readOutbox(key = outboxKey()): PendingInteraction[] {
  try {
    const value = JSON.parse(localStorage.getItem(key) || "[]");
    return Array.isArray(value) ? value : [];
  } catch { return []; }
}

export function pendingInteractionCount(): number {
  return readOutbox().length;
}

function notifyQueue() {
  window.dispatchEvent(new Event("merrec:interaction-queue-changed"));
}

let flushing: Promise<boolean> | null = null;
let flushingKey: string | null = null;

export function flushPendingInteractions(): Promise<boolean> {
  const key = outboxKey();
  if (flushing) {
    const previousKey = flushingKey;
    return flushing.then((saved) => previousKey === key ? saved : flushPendingInteractions());
  }
  flushingKey = key;
  const token = localStorage.getItem("merrec_token");
  flushing = (async () => {
    let saved = 0;
    const rejected = new Set<string>();
    for (let attempts = 0; attempts < 100; attempts += 1) {
      if (outboxKey() !== key) break;
      const next = readOutbox(key).find(event => !rejected.has(event.event_key));
      if (!next) break;
      try {
        const response = await fetch("/api/events", {
          method: "POST",
          headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
          body: JSON.stringify(next),
          cache: "no-store",
          keepalive: true,
          signal: AbortSignal.timeout(15000),
        });
        if (response.status === 403) {
          // Keep an old, rejected attribution for diagnosis without blocking
          // valid interactions belonging to the current feed.
          rejected.add(next.event_key);
          continue;
        }
        if (!response.ok) break;
        const receipt = await response.json();
        if (receipt.status !== "success" || !receipt.event_id) break;
        const remaining = readOutbox(key).filter((event) => event.event_key !== next.event_key);
        localStorage.setItem(key, JSON.stringify(remaining));
        if (next.event_type !== "impression") saved += 1;
        notifyQueue();
      } catch { break; }
    }
    if (saved) window.dispatchEvent(new Event("merrec:interaction-saved"));
    return readOutbox(key).length === 0;
  })().finally(() => { flushing = null; flushingKey = null; notifyQueue(); });
  return flushing;
}

export async function fetchRecommendationsClient(
  context = "home",
  triggerItemId?: string | null,
  limit = 12,
  excludeItemIds?: string[],
  options: { cursor?: string | null; signal?: AbortSignal } = {}
): Promise<RecommendationResponse> {
  const url = new URL("/api/recommendations", window.location.origin);
  url.searchParams.set("context", context);
  if (triggerItemId) url.searchParams.set("trigger_item_id", triggerItemId);
  url.searchParams.set("limit", String(limit));
  if (options.cursor) url.searchParams.set("cursor", options.cursor);
  if (excludeItemIds && excludeItemIds.length > 0) {
    url.searchParams.set("exclude_item_ids", excludeItemIds.join(","));
  }

  const token = localStorage.getItem("merrec_token");
  // A visible feed remains owned by its original session even after the
  // browsing session's inactivity timeout. Never send a new session with its cursor.
  let sessionId = (options.cursor && requestSession(options.cursor.split(":")[0])) || recommendationSession();
  const headers: Record<string, string> = { "X-Merrec-Session": sessionId };
  if (token) headers.Authorization = `Bearer ${token}`;
  // Recommendation reads use saved server history while the durable client
  // outbox retries independently. An event outage must not block the feed.
  if (context === "home" && !options.cursor) void flushPendingInteractions();
  const timeout = AbortSignal.timeout(47000);
  let res = await fetch(url.toString(), { cache: "no-store", headers,
    signal: options.signal ? AbortSignal.any([options.signal, timeout]) : timeout });
  if (context === "home" && !options.cursor && res.status === 403) {
    // Cookie/account changes can leave a browsing session bound to an old
    // identity. Start a new feed, keeping authorization checks on the server.
    sessionStorage.removeItem("merrec_recommendation_session");
    sessionId = recommendationSession();
    headers["X-Merrec-Session"] = sessionId;
    res = await fetch(url.toString(), { cache: "no-store", headers,
      signal: options.signal ? AbortSignal.any([options.signal, timeout]) : timeout });
  }
  if (!res.ok) {
    throw new Error(res.status === 410 || (options.cursor && [403, 404].includes(res.status)) ? "Danh sách đã hết hạn. Vui lòng tải lại gợi ý." : "Chưa tải được gợi ý. Vui lòng thử lại.");
  }

  const data: RecommendationResponse = await res.json();
  data.session_id = sessionId;
  rememberRequestSession(data.request_id, sessionId);
  if (data.next_cursor) rememberRequestSession(data.next_cursor.split(":")[0], sessionId);

  if (excludeItemIds && excludeItemIds.length > 0 && Array.isArray(data.items)) {
    data.items = data.items.filter((item) => !excludeItemIds.includes(item.id));
  }

  return data;
}

export interface RecommendationAttribution {
  recommendation_request_id: string;
  position: number;
  session_id: string;
  saved_at: number;
}

export function rememberRecommendation(itemId: string, requestId: string, position: number) {
  try {
    const key = `merrec_attribution:${outboxKey()}`;
    const records = JSON.parse(sessionStorage.getItem(key) || "{}");
    const now = Date.now();
    for (const [id, value] of Object.entries(records)) {
      if (now - (value as RecommendationAttribution).saved_at > 30 * 60 * 1000) delete records[id];
    }
    records[itemId] = { recommendation_request_id: requestId, position, session_id: requestSession(requestId) || recommendationSession(), saved_at: now };
    sessionStorage.setItem(key, JSON.stringify(records));
  } catch { /* Events still use explicit attribution when available. */ }
}

function rememberedRecommendation(itemId: string): RecommendationAttribution | undefined {
  try {
    const records = JSON.parse(sessionStorage.getItem(`merrec_attribution:${outboxKey()}`) || "{}");
    const value: RecommendationAttribution | undefined = records[itemId];
    if (value && Date.now() - value.saved_at <= 30 * 60 * 1000) return value;
  } catch { /* No stale attribution. */ }
}

export async function trackEventClient(payload: {
  item_id: string;
  event_type: "impression" | "view" | "click" | "like" | "unlike" | "cart" | "offer" | "offer_make" | "buy_start" | "buy_comp";
  source_page?: string;
  recommendation_request_id?: string;
  position?: number;
  metadata?: Record<string, unknown>;
}) {
  try {
    const key = outboxKey();
    const attribution = payload.recommendation_request_id ? undefined : rememberedRecommendation(payload.item_id);
    const next: PendingInteraction = { ...payload,
      ...(attribution ? { recommendation_request_id: attribution.recommendation_request_id, position: attribution.position } : {}),
      session_id: attribution?.session_id || (payload.recommendation_request_id && requestSession(payload.recommendation_request_id)) || recommendationSession(), event_key: crypto.randomUUID() };
    // Persist before navigating away. The same key is reused if the request times out after commit.
    localStorage.setItem(key, JSON.stringify([...readOutbox(key), next]));
    notifyQueue();
    return await flushPendingInteractions();
  } catch {
    notifyQueue();
    return false;
  }
}
