export interface ProductImageResult { url: string; source: string; title: string }
const requests = new Map<string, Promise<ProductImageResult[]>>();
let running = 0;
const queue: (() => void)[] = [];

// Only expose decoded images to the gallery, never broken thumbnail placeholders.
async function canDisplay(url: string): Promise<boolean> {
  return new Promise((resolve) => {
    const image = new Image();
    const finish = (ok: boolean) => {
      clearTimeout(timer);
      image.onload = image.onerror = null;
      resolve(ok);
    };
    const timer = setTimeout(() => finish(false), 8000);
    image.referrerPolicy = "no-referrer";
    image.onload = () => finish(image.naturalWidth > 0);
    image.onerror = () => finish(false);
    image.src = url;
  });
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
          const resolved = Promise.resolve(parsed);
          requests.set(id, resolved);
          return resolved;
        }
      }
    } catch {}
  }

  const result = (async () => {
    if (running >= 3) await new Promise<void>((resolve) => queue.push(resolve)); else running++;
    try {
      const response = await fetch(`/api/products/${encodeURIComponent(id)}/images`);
      if (!response.ok) throw new Error("Không thể tìm ảnh lúc này");
      const data = await response.json();
      const candidates = (data.images || []) as ProductImageResult[];
      const loaded = await Promise.all(candidates.map((image) => canDisplay(image.url)));
      const finalImages = candidates.filter((_, index) => loaded[index]);

      if (typeof window !== "undefined" && finalImages.length > 0) {
        try {
          sessionStorage.setItem(`merrec_img_${id}`, JSON.stringify(finalImages));
        } catch {}
      }
      return finalImages;
    } finally {
      const next = queue.shift();
      if (next) next(); else running--;
    }
  })();

  requests.set(id, result);
  result.catch(() => requests.delete(id));
  return result;
}
