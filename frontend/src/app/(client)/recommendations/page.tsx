import ProductCard from "@/components/productcard/ProductCard";
import { MERREC_PRODUCTS } from "@/lib/merrecData";

export const metadata = {
  title: "Gợi ý dành riêng cho bạn | KDZino",
};

export default function RecommendationsPage() {
  return (
    <div className="container-custom" style={{ padding: "30px 0" }}>
      <div
        style={{
          background: "white",
          padding: "24px",
          borderRadius: "12px",
          border: "1px solid #eaeaea",
          marginBottom: "24px",
        }}
      >
        <h1 style={{ fontSize: "22px", fontWeight: 800, color: "#088751", marginBottom: "8px" }}>
          ✨ Gợi ý dành riêng cho bạn
        </h1>
        <p style={{ color: "#666", fontSize: "14px" }}>
          Hệ thống MerRec AI phân tích xu hướng mua sắm để gợi ý những sản phẩm phù hợp nhất với sở thích của bạn.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: "16px" }}>
        {MERREC_PRODUCTS.map((product) => (
          <ProductCard key={product.id} product={product} />
        ))}
      </div>
    </div>
  );
}
