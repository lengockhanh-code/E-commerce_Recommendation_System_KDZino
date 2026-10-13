import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { type Product } from "./merrecData";

const root = path.resolve(process.cwd(), "..");
const venv = path.join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const python = process.env.MERREC_PYTHON || (existsSync(venv) ? venv : "python");
let active = 0;
const waiting: (() => void)[] = [];

async function bridge<T>(args: string[], input?: unknown): Promise<T> {
  if (active >= 4) {
    if (waiting.length >= 50) throw new Error("Catalog service is busy");
    await new Promise<void>((resolve) => waiting.push(resolve));
  } else active++;
  try {
    return await new Promise<T>((resolve, reject) => {
      const child = execFile(python, [path.join(root, "scripts/storefront_catalog.py"), ...args],
        { cwd: root, timeout: 45000, maxBuffer: 4 * 1024 * 1024, windowsHide: true, encoding: "utf8" },
        (error, stdout) => {
          if (error) return reject(error);
          try { resolve(JSON.parse(stdout)); } catch (error) { reject(error); }
        });
      child.stdin?.end(input ? JSON.stringify(input) : undefined);
    });
  } finally {
    const next = waiting.shift();
    if (next) next(); else active--;
  }
}

export async function getProduct(id: string): Promise<Product | null> {
  if (!id || typeof id !== "string") return null;
  return bridge<Product | null>(["detail", id.trim()]);
}

export interface SearchImage { url: string; source: string; title: string; reference?: boolean }
const cache = new Map<string, { expires: number; promise: Promise<SearchImage[]> }>();
let nextSync = 0;
export async function findImages(product: Product) {
  if (Date.now() >= nextSync) {
    nextSync = Date.now() + 60000;
    // Outbox recovery must not delay an image response during a DB outage.
    void bridge(["sync-images"]).catch(() => {});
  }
  const existing = cache.get(product.id);
  if (existing && existing.expires > Date.now()) return existing.promise;
  if (cache.size >= 500) cache.delete(cache.keys().next().value!);
  const promise = bridge<SearchImage[]>(["images"], product).then((images) => {
    if (!images.length) cache.delete(product.id);
    else if (images.some((image) => image.reference)) {
      const entry = cache.get(product.id);
      if (entry) entry.expires = Date.now() + 60000;
    }
    return images;
  }).catch((error) => { cache.delete(product.id); throw error; });
  cache.set(product.id, { expires: Date.now() + 3600000, promise });
  return promise;
}

export interface RecommendationResult {
  request_id: string;
  context: string;
  trigger_item_id: string | null;
  model_name: string;
  items: (Product & { score?: number })[];
}

const recCache = new Map<string, { expires: number; promise: Promise<RecommendationResult> }>();

export async function fetchRecommendations(
  context = "home",
  triggerItemId: string | null = null,
  limit = 12,
  sessionId: string | null = null,
  userId: string | null = null
): Promise<RecommendationResult> {
  const cacheKey = `${context}:${triggerItemId || "null"}:${limit}:${sessionId || "null"}:${userId || "null"}`;
  const existing = recCache.get(cacheKey);
  if (existing && existing.expires > Date.now()) {
    return existing.promise;
  }
  if (recCache.size >= 200) recCache.delete(recCache.keys().next().value!);
  const promise = bridge<RecommendationResult>([
    "recommendations",
    context,
    triggerItemId ?? "null",
    String(limit),
    sessionId ?? "null",
    userId ?? "null"
  ]);
  recCache.set(cacheKey, { expires: Date.now() + 15000, promise }); // 15 sec cache to react quickly to new interactions
  promise.catch(() => recCache.delete(cacheKey));
  return promise;
}

export interface UserEventPayload {
  item_id: string;
  event_type: string;
  user_id?: string;
  session_id?: string;
  source_page?: string;
  recommendation_request_id?: string;
  position?: number;
  metadata?: Record<string, unknown>;
}

export async function logUserEvent(payload: UserEventPayload): Promise<{ status: string }> {
  return bridge<{ status: string }>(["log-event"], payload);
}

export interface OrderItemPayload {
  item_id: string;
  product_name?: string;
  quantity: number;
  unit_price: number;
}

export interface CreateOrderPayload {
  user_id?: string;
  total_amount: number;
  shipping_address?: Record<string, unknown>;
  payment_method?: string;
  items: OrderItemPayload[];
}

export async function createOrder(payload: CreateOrderPayload): Promise<{ status: string; order_id: string }> {
  return bridge<{ status: string; order_id: string }>(["create-order"], payload);
}
