import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { MERREC_PRODUCTS, type Product } from "./merrecData";

const root = path.resolve(process.cwd(), "..");
const venv = path.join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const python = process.env.MERREC_PYTHON || (existsSync(venv) ? venv : "python");
let active = 0;
const waiting: (() => void)[] = [];

async function bridge<T>(args: string[], input?: unknown): Promise<T> {
  if (active >= 2) {
    if (waiting.length >= 30) throw new Error("Catalog is busy");
    await new Promise<void>((resolve) => waiting.push(resolve));
  } else active++;
  try {
    return await new Promise<T>((resolve, reject) => {
      const child = execFile(python, [path.join(root, "scripts/storefront_catalog.py"), ...args],
        { cwd: root, timeout: 45000, maxBuffer: 2 * 1024 * 1024, windowsHide: true, encoding: "utf8" },
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
  if (!/^\d{1,20}$/.test(id)) return null;
  return MERREC_PRODUCTS.find((product) => product.id === id) ?? bridge<Product | null>(["detail", id]);
}

export interface SearchImage { url: string; source: string; title: string }
const cache = new Map<string, { expires: number; promise: Promise<SearchImage[]> }>();
let nextSync = 0;
export async function findImages(product: Product) {
  // Retry the durable outbox even when this request is served from memory.
  if (Date.now() >= nextSync) {
    nextSync = Date.now() + 60000;
    await bridge(["sync-images"]).catch(() => {});
  }
  const existing = cache.get(product.id);
  if (existing && existing.expires > Date.now()) return existing.promise;
  if (cache.size >= 500) cache.delete(cache.keys().next().value!);
  const promise = bridge<SearchImage[]>(["images"], product).then((images) => {
    if (!images.length) cache.delete(product.id);
    return images;
  }).catch((error) => { cache.delete(product.id); throw error; });
  cache.set(product.id, { expires: Date.now() + 3600000, promise });
  return promise;
}
