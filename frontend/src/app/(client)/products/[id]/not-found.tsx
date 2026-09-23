import Link from "next/link";

export default function ProductNotFound() {
  return <section style={{ padding: "80px 24px", textAlign: "center", minHeight: 400 }}>
    <h1>Không tìm thấy sản phẩm</h1>
    <p style={{ margin: "15px 0 25px", color: "#78847b" }}>Sản phẩm có thể không còn trong danh mục hoặc đường dẫn đã cũ.</p>
    <Link href="/products" style={{ background: "#008d54", color: "white", padding: "12px 24px", borderRadius: 6 }}>Xem danh mục sản phẩm</Link>
  </section>;
}
