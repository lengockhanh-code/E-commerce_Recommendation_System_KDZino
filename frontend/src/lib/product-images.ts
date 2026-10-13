export interface ProductImageResult { url: string; source: string; title: string; reference?: boolean }
const requests = new Map<string, Promise<ProductImageResult[]>>();
let running = 0;
const queue: (() => void)[] = [];

export function productImageUrls(values: unknown[]): string[] {
  return [...new Set(values.filter((value): value is string =>
    typeof value === "string" &&
    (value.startsWith("https://") || (value.startsWith("/") && !value.startsWith("//"))) &&
    !["/placeholder.svg", "/products/demo.png"].includes(value)
  ))];
}

export function loadProductImages(id: string, retry = false) {
  if (retry) {
    requests.delete(id);
    if (typeof window !== "undefined") {
      try { sessionStorage.removeItem(`merrec_img_${id}`); } catch {}
    }
  }

  // 1. Check in-memory Map cache
  const existing = requests.get(id);
  if (existing) return existing;

  // 2. Check durable sessionStorage cache
  if (typeof window !== "undefined" && !retry) {
    try {
      const cached = sessionStorage.getItem(`merrec_img_${id}`);
      if (cached) {
        const parsed = JSON.parse(cached);
        if (Array.isArray(parsed) && parsed.length > 0) {
          const images = parsed.filter((entry): entry is ProductImageResult =>
            entry && productImageUrls([entry.url]).length > 0);
          if (images.length) {
            const resolved = Promise.resolve(images);
            requests.set(id, resolved);
            return resolved;
          }
        }
      }
    } catch {}
  }

  const result = (async () => {
    if (running >= 4) await new Promise<void>((resolve) => queue.push(resolve)); else running++;
    try {
      const response = await fetch(`/api/products/${encodeURIComponent(id)}/images`, {
        cache: retry ? "reload" : "default",
        signal: AbortSignal.timeout(90000),
      });
      if (!response.ok) throw new Error("Không thể tìm ảnh lúc này");
      const data = await response.json();
      const candidates: ProductImageResult[] = Array.isArray(data.images)
        ? data.images.filter((entry: ProductImageResult) => entry && productImageUrls([entry.url]).length > 0)
        : [];

      if (typeof window !== "undefined" && candidates.length > 0 && !candidates.some((image) => image.reference)) {
        try {
          sessionStorage.setItem(`merrec_img_${id}`, JSON.stringify(candidates));
        } catch {}
      }
      return candidates;
    } finally {
      running--;
      const next = queue.shift();
      if (next) {
        running++;
        next();
      }
    }
  })();

  requests.set(id, result);
  const forget = () => { if (requests.get(id) === result) requests.delete(id); };
  result.then((images) => { if (!images.length || images.some((image) => image.reference)) forget(); }, forget);
  return result;
}
