"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Plus,
  Search,
  Filter,
  Trash2,
  Edit,
  Eye,
  CheckCircle,
  AlertCircle
} from "lucide-react";
import { formatPrice } from "@/lib/merrecData";

interface SellerProduct {
  item_id: string;
  name: string;
  price: number;
  original_price?: number;
  category0?: string;
  brand?: string;
  stock?: number;
  sku?: string;
  is_active?: boolean;
  images: string[];
}

export default function SellerProductsPage() {
  const [products, setProducts] = useState<SellerProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [statusMessage, setStatusMessage] = useState("");

  const fetchProducts = () => {
    setLoading(true);
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
    let url = `${apiBase}/seller/products?page_size=50`;
    if (search.trim()) url += `&q=${encodeURIComponent(search.trim())}`;
    if (categoryFilter !== "all") url += `&category=${encodeURIComponent(categoryFilter)}`;

    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load products");
        return res.json();
      })
      .then((data) => {
        setProducts(data.products || []);
      })
      .catch((err) => {
        console.warn("Product list fallback:", err);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchProducts();
  }, [categoryFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchProducts();
  };

  const handleDelete = async (itemId: string, name: string) => {
    if (!confirm(`Bạn có chắc chắn muốn xóa sản phẩm "${name}"?`)) return;

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const res = await fetch(`${apiBase}/seller/products/${itemId}`, {
        method: "DELETE"
      });

      if (!res.ok) throw new Error("Không thể xóa sản phẩm");

      setStatusMessage(`Đã xóa sản phẩm "${name}" thành công.`);
      setProducts((prev) => prev.filter((p) => p.item_id !== itemId));
      setTimeout(() => setStatusMessage(""), 4000);
    } catch (err: any) {
      alert(err.message || "Lỗi xóa sản phẩm");
    }
  };

  return (
    <div className="seller-products-page">
      {/* HEADER ROW */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "20px" }}>
        <div>
          <h1 style={{ fontSize: "24px", fontWeight: 800, color: "#111827", margin: "0 0 6px 0" }}>
            Quản lý sản phẩm
          </h1>
          <p style={{ fontSize: "13.5px", color: "#6b7280", margin: 0 }}>
            Xem, chỉnh sửa tồn kho và tối ưu hóa các sản phẩm trong gian hàng của bạn
          </p>
        </div>

        <Link
          href="/seller/products/new"
          className="seller-btn-primary"
          style={{ textDecoration: "none" }}
        >
          <Plus size={18} />
          <span>Thêm sản phẩm mới</span>
        </Link>
      </div>

      {statusMessage && (
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          padding: "12px 16px",
          background: "#dcfce7",
          border: "1px solid #bbf7d0",
          borderRadius: "8px",
          color: "#166534",
          fontSize: "14px",
          marginBottom: "16px"
        }}>
          <CheckCircle size={18} />
          <span>{statusMessage}</span>
        </div>
      )}

      {/* FILTER & SEARCH BAR */}
      <div style={{
        background: "#ffffff",
        border: "1px solid #e5e7eb",
        borderRadius: "10px",
        padding: "16px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "16px",
        marginBottom: "20px",
        flexWrap: "wrap"
      }}>
        <form onSubmit={handleSearchSubmit} style={{ display: "flex", alignItems: "center", gap: "8px", flex: 1, minWidth: "260px" }}>
          <div style={{ position: "relative", width: "100%" }}>
            <input
              type="text"
              placeholder="Tìm kiếm theo tên sản phẩm, mã SKU..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="seller-input"
              style={{ paddingLeft: "36px" }}
            />
            <Search size={16} color="#9ca3af" style={{ position: "absolute", left: "12px", top: "12px" }} />
          </div>
          <button type="submit" className="seller-btn-secondary" style={{ padding: "9px 16px" }}>
            Tìm kiếm
          </button>
        </form>

        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <Filter size={16} color="#6b7280" />
            <span style={{ fontSize: "13px", color: "#4b5563", fontWeight: 500 }}>Danh mục:</span>
          </div>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="seller-select"
            style={{ width: "auto", minWidth: "160px" }}
          >
            <option value="all">Tất cả danh mục</option>
            <option value="Thời trang">Thời trang</option>
            <option value="Giày dép">Giày dép</option>
            <option value="Điện tử">Điện tử</option>
            <option value="Mỹ phẩm">Mỹ phẩm</option>
            <option value="Đồ gia dụng">Đồ gia dụng</option>
          </select>
        </div>
      </div>

      {/* PRODUCTS TABLE */}
      <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: "12px", overflow: "hidden" }}>
        {loading ? (
          <div style={{ padding: "40px", textAlign: "center", color: "#6b7280" }}>
            Đang tải danh sách sản phẩm...
          </div>
        ) : products.length === 0 ? (
          <div style={{ padding: "50px 20px", textAlign: "center" }}>
            <p style={{ fontSize: "15px", color: "#4b5563", marginBottom: "16px" }}>
              Chưa có sản phẩm nào trong danh mục hoặc tìm kiếm này.
            </p>
            <Link href="/seller/products/new" className="seller-btn-primary" style={{ textDecoration: "none" }}>
              <Plus size={16} />
              <span>Đăng sản phẩm ngay</span>
            </Link>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="seller-table">
              <thead>
                <tr>
                  <th style={{ width: "40%" }}>Sản phẩm</th>
                  <th>SKU</th>
                  <th>Danh mục</th>
                  <th>Giá bán</th>
                  <th>Tồn kho</th>
                  <th>Trạng thái</th>
                  <th style={{ textAlign: "right" }}>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {products.map((p) => {
                  const coverImg = p.images && p.images.length > 0 ? p.images[0] : "/placeholder.svg";
                  const inStock = (p.stock || 0) > 0;
                  return (
                    <tr key={p.item_id}>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                          <img
                            src={coverImg}
                            alt={p.name}
                            style={{ width: "48px", height: "48px", borderRadius: "6px", objectFit: "cover", background: "#f3f4f6" }}
                          />
                          <div>
                            <div style={{ fontWeight: 600, color: "#111827", fontSize: "13.5px" }}>
                              {p.name}
                            </div>
                            <div style={{ fontSize: "12px", color: "#6b7280" }}>
                              {p.brand || "—"}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td style={{ color: "#4b5563", fontSize: "12.5px" }}>
                        {p.sku || p.item_id}
                      </td>
                      <td>
                        <span style={{ padding: "3px 8px", background: "#f3f4f6", borderRadius: "4px", fontSize: "12px", color: "#374151" }}>
                          {p.category0 || "Chung"}
                        </span>
                      </td>
                      <td style={{ fontWeight: 700, color: "#008848" }}>
                        {formatPrice(p.price)}
                      </td>
                      <td>
                        <span style={{ fontWeight: 600, color: inStock ? "#111827" : "#dc2626" }}>
                          {p.stock !== undefined ? p.stock : 100}
                        </span>
                      </td>
                      <td>
                        <span
                          className={`seller-status-badge ${inStock ? "seller-status-completed" : "seller-status-cancelled"}`}
                        >
                          ● {inStock ? "Đang bán" : "Hết hàng"}
                        </span>
                      </td>
                      <td style={{ textAlign: "right" }}>
                        <div style={{ display: "inline-flex", gap: "8px" }}>
                          <Link
                            href={`/products/${p.item_id}`}
                            target="_blank"
                            title="Xem trên shop"
                            style={{
                              padding: "6px",
                              borderRadius: "6px",
                              border: "1px solid #e5e7eb",
                              color: "#4b5563",
                              display: "flex",
                              alignItems: "center"
                            }}
                          >
                            <Eye size={14} />
                          </Link>
                          <button
                            type="button"
                            title="Xóa sản phẩm"
                            onClick={() => handleDelete(p.item_id, p.name)}
                            style={{
                              padding: "6px",
                              borderRadius: "6px",
                              border: "1px solid #fee2e2",
                              background: "#fef2f2",
                              color: "#dc2626",
                              cursor: "pointer",
                              display: "flex",
                              alignItems: "center"
                            }}
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
