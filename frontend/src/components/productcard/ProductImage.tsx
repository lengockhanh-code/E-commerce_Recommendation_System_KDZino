"use client";
import { useEffect, useRef, useState } from "react";
import { ImageIcon } from "lucide-react";
import { loadProductImages } from "@/lib/product-images";

export default function ProductImage({ id, name, src, fit = "cover" }: { id: string; name: string; src?: string; fit?: "cover" | "contain" }) {
  const ref = useRef<HTMLDivElement>(null);
  const [urls, setUrls] = useState<string[]>(src ? [src] : []);
  const [index, setIndex] = useState(0);
  const [finished, setFinished] = useState(false);
  useEffect(() => {
    if (src) return;
    let cancelled = false;
    const observer = new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      observer.disconnect();
      loadProductImages(id).then((images) => { if (!cancelled) setUrls(images.map((image) => image.url)); })
        .catch(() => {}).finally(() => { if (!cancelled) setFinished(true); });
    });
    if (ref.current) observer.observe(ref.current);
    return () => { cancelled = true; observer.disconnect(); };
  }, [id, src]);
  return <div ref={ref} style={{ width: "100%", height: "100%", minHeight: 90, display: "grid", placeItems: "center", background: "#f7faf8" }}>
    {urls[index] ? <img src={urls[index]} alt={name} loading="lazy" referrerPolicy="no-referrer" onError={() => setIndex((value) => value + 1)} style={{ width: "100%", height: "100%", objectFit: fit }} />
      : <span style={{ display: "grid", justifyItems: "center", gap: 8, color: "#84968d", fontSize: 12 }}><ImageIcon size={26} strokeWidth={1} />{finished ? "Chưa có ảnh" : "Đang tìm ảnh…"}</span>}
  </div>;
}
