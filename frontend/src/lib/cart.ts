import { useSyncExternalStore } from "react";
import type { Product } from "./merrecData";
export interface CartItem { product: Product; qty: number }
const KEY = "kdzino-cart-v1";
const EMPTY: CartItem[] = [];
let lastRaw: string | null = null;
let lastItems = EMPTY;
function read(): CartItem[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw === lastRaw) return lastItems;
    lastRaw = raw;
    const parsed = raw ? JSON.parse(raw) : [];
    lastItems = Array.isArray(parsed) ? parsed.filter((item) => item?.product?.id && Number.isInteger(item.qty) && item.qty > 0) : EMPTY;
    return lastItems;
  } catch { return EMPTY; }
}
function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener("cart-change", callback);
  return () => { window.removeEventListener("storage", callback); window.removeEventListener("cart-change", callback); };
}
export function saveCart(items: CartItem[]) {
  localStorage.setItem(KEY, JSON.stringify(items));
  window.dispatchEvent(new Event("cart-change"));
}
export function addToCart(product: Product, qty: number) {
  const items = read();
  const found = items.find((item) => item.product.id === product.id);
  const limit = product.stockKnown ? product.stockCount : 99;
  if (!Number.isInteger(qty) || qty < 1 || (found?.qty || 0) + qty > limit) throw new Error(`Bạn có thể thêm tối đa ${limit} sản phẩm vào giỏ.`);
  saveCart(found ? items.map((item) => item.product.id === product.id ? { ...item, qty: item.qty + qty } : item) : [...items, { product, qty }]);
}
export function useCart() {
  const items = useSyncExternalStore(subscribe, read, () => EMPTY);
  return { items, update: (change: (items: CartItem[]) => CartItem[]) => saveCart(change(read())) };
}
