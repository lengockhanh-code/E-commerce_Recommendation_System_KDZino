"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ImageIcon } from "lucide-react";
import { loadProductImages, productImageUrls } from "@/lib/product-images";

interface Props {
  id: string;
  name: string;
  src?: string;
  sources?: string[];
  href?: string;
  fit?: "cover" | "contain";
}

export default function ProductImage(props: Props) {
  const urls = productImageUrls([props.src, ...(props.sources || [])]);
  return <ImageLoader key={JSON.stringify([props.id, urls])} {...props} initialUrls={urls} />;
}

function ImageLoader({ id, name, href, fit = "cover", initialUrls }: Props & { initialUrls: string[] }) {
  const [urls, setUrls] = useState(initialUrls);
  const [index, setIndex] = useState(0);
  const [resolved, setResolved] = useState(false);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [reference, setReference] = useState(false);
  const current = urls[index];

  useEffect(() => {
    if (current || resolved) return;
    let cancelled = false;
    loadProductImages(id, attempt > 0).then((images) => {
      if (!cancelled) {
        setUrls(images.map((image) => image.url));
        setReference(images.some((image) => image.reference));
        setIndex(0);
        setResolved(true);
      }
    }).catch(() => {
      if (!cancelled) { setFailed(true); setResolved(true); }
    });
    return () => { cancelled = true; };
  }, [id, current, resolved, attempt]);

  const visual = current ? (
    <img src={current} alt={name} loading="lazy" referrerPolicy="no-referrer"
      onError={() => setIndex((value) => value + 1)}
      style={{ width: "100%", height: "100%", objectFit: fit }} />
  ) : (
    <span role="status" style={{ display: "grid", justifyItems: "center", gap: 8, color: "#84968d", fontSize: 12 }}>
      <ImageIcon size={26} strokeWidth={1} />
      {!resolved ? "Đang tìm ảnh…" : failed ? "Chưa tải được ảnh" : "Chưa có ảnh phù hợp"}
    </span>
  );

  return <div style={{ position: "relative", width: "100%", height: "100%", minHeight: 90, display: "grid", placeItems: "center", background: "#f7faf8" }}>
    {href ? <Link href={href} aria-label={`Xem ${name}`} style={{ display: "grid", placeItems: "center", width: "100%", height: "100%" }}>{visual}</Link> : visual}
    {current && reference && <span style={{ position: "absolute", bottom: 6, background: "#fff", padding: "3px 7px", fontSize: 11 }} title="Ảnh của sản phẩm cùng loại; chưa có ảnh riêng của sản phẩm này">Ảnh tham khảo</span>}
    {!current && resolved && <button type="button" aria-label={`Thử tải lại ảnh ${name}`}
      style={{ position: "absolute", bottom: 6, fontSize: 12, padding: "4px 8px", cursor: "pointer" }}
      onClick={(event) => {
        event.preventDefault(); event.stopPropagation();
        setFailed(false); setResolved(false); setAttempt((value) => value + 1);
      }}>Thử lại ảnh</button>}
  </div>;
}
