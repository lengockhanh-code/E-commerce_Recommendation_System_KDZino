import { NextRequest, NextResponse } from "next/server";
import { MERREC_PRODUCTS } from "@/lib/merrecData";
import {
  matchProductQuery,
  CAT_DISPLAY_MAP,
} from "@/lib/searchMatcher";

export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const query = (searchParams.get("q") || "").trim();

  if (!query) {
    return NextResponse.json({ query: "", products: [], categories: [], total: 0 });
  }

  const matchedProducts: Array<{
    id: string;
    name: string;
    price: number;
    originalPrice: number;
    image: string;
    category: string;
    brand: string;
  }> = [];
  const seenIds = new Set<string>();

  // 1. Fetch from FastAPI backend (which queries PostgreSQL dataset with verified images)
  try {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
    const res = await fetch(`${apiBase}/products?q=${encodeURIComponent(query)}&page_size=8`, {
      cache: "no-store",
      signal: AbortSignal.timeout(2000),
    });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data.products)) {
        for (const p of data.products) {
          if (!seenIds.has(p.item_id)) {
            seenIds.add(p.item_id);
            const catName = p.category0 || "";
            matchedProducts.push({
              id: p.item_id,
              name: p.name,
              price: p.price,
              originalPrice: p.original_price || p.price,
              image: (p.images && p.images[0]) || "/placeholder.svg",
              category: CAT_DISPLAY_MAP[catName] || catName || "Sản phẩm",
              brand: p.brand || "",
            });
          }
        }
      }
    }
  } catch {
    // If backend is unreachable, gracefully fallback to local dataset
  }

  // 2. Also search local MERREC_PRODUCTS if needed to supplement
  if (matchedProducts.length < 8) {
    for (const p of MERREC_PRODUCTS) {
      if (seenIds.has(p.id)) continue;

      if (matchProductQuery(p, query)) {
        seenIds.add(p.id);
        const catName = p.c0_name || "";
        matchedProducts.push({
          id: p.id,
          name: p.name,
          price: p.price,
          originalPrice: p.originalPrice || p.price,
          image: p.image || (p.images && p.images[0]) || "/placeholder.svg",
          category: CAT_DISPLAY_MAP[catName] || catName || "Sản phẩm",
          brand: p.brand || "",
        });
        if (matchedProducts.length >= 8) break;
      }
    }
  }

  // Extract matching categories for suggestions
  const categories = Array.from(
    new Set(matchedProducts.map((p) => p.category).filter(Boolean))
  ).slice(0, 3);

  return NextResponse.json({
    query,
    products: matchedProducts.slice(0, 8),
    categories,
    total: matchedProducts.length,
  });
}
