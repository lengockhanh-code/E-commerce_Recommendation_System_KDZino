import { type Product } from "./merrecData";

export interface RecommendationResponse {
  request_id: string;
  context: string;
  trigger_item_id: string | null;
  model_name: string;
  degraded?: boolean;
  segment?: string;
  candidate_count?: number;
  model_status?: Record<string, string>;
  items: (Product & { score?: number })[];
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
  event_type: "view" | "click" | "like" | "unlike" | "cart" | "offer" | "buy_start" | "buy_comp";
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

export function flushPendingInteractions(): Promise<boolean> {
  if (flushing) return flushing;
  const key = outboxKey();
  const token = localStorage.getItem("merrec_token");
  flushing = (async () => {
    let saved = 0;
    for (let attempts = 0; attempts < 100; attempts += 1) {
      const next = readOutbox(key)[0];
      if (!next) break;
      try {
        const response = await fetch("/api/events", {
          method: "POST",
          headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
          body: JSON.stringify(next),
          cache: "no-store",
          keepalive: true,
          signal: AbortSignal.timeout(10000),
        });
        if (!response.ok) break;
        const remaining = readOutbox(key).filter((event) => event.event_key !== next.event_key);
        localStorage.setItem(key, JSON.stringify(remaining));
        saved += 1;
        notifyQueue();
      } catch { break; }
    }
    if (saved) window.dispatchEvent(new Event("merrec:interaction-saved"));
    return readOutbox(key).length === 0;
  })().finally(() => { flushing = null; notifyQueue(); });
  return flushing;
}

export async function fetchRecommendationsClient(
  context = "home",
  triggerItemId?: string | null,
  limit = 12,
  excludeItemIds?: string[]
): Promise<RecommendationResponse> {
  const url = new URL("/api/recommendations", window.location.origin);
  url.searchParams.set("context", context);
  if (triggerItemId) url.searchParams.set("trigger_item_id", triggerItemId);
  url.searchParams.set("limit", String(limit));
  if (excludeItemIds && excludeItemIds.length > 0) {
    url.searchParams.set("exclude_item_ids", excludeItemIds.join(","));
  }

  const token = localStorage.getItem("merrec_token");
  const headers: Record<string, string> = { "X-Merrec-Session": recommendationSession() };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (context === "home" && !(await flushPendingInteractions())) {
    throw new Error("Tương tác chưa được lưu. Vui lòng thử đồng bộ trước khi tải gợi ý mới.");
  }
  const res = await fetch(url.toString(), { cache: "no-store", headers, signal: AbortSignal.timeout(47000) });
  if (!res.ok) {
    throw new Error("Failed to fetch recommendations");
  }

  const data: RecommendationResponse = await res.json();

  if (excludeItemIds && excludeItemIds.length > 0 && Array.isArray(data.items)) {
    data.items = data.items.filter((item) => !excludeItemIds.includes(item.id));
  }

  return data;
}

export async function trackEventClient(payload: {
  item_id: string;
  event_type: "view" | "click" | "like" | "unlike" | "cart" | "offer" | "buy_start" | "buy_comp";
  source_page?: string;
  recommendation_request_id?: string;
  position?: number;
  metadata?: Record<string, unknown>;
}) {
  try {
    const key = outboxKey();
    const next: PendingInteraction = { ...payload, session_id: recommendationSession(), event_key: crypto.randomUUID() };
    // Persist before navigating away. The same key is reused if the request times out after commit.
    localStorage.setItem(key, JSON.stringify([...readOutbox(key), next]));
    notifyQueue();
    return await flushPendingInteractions();
  } catch {
    notifyQueue();
    return false;
  }
}
