"use client";
import Link from "next/link";
export default function ProductError({ reset }: { reset: () => void }) {
  return <section style={{ padding: "80px 24px", textAlign: "center" }}><h1>Chưa tải được sản phẩm</h1><p>Vui lòng thử lại sau giây lát.</p><button onClick={reset} style={{ padding: "12px 24px", margin: 20 }}>Thử lại</button><Link href="/products">Về danh sách sản phẩm</Link></section>;
}
