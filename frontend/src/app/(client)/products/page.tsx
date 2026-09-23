"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import ProductCard from "@/components/productcard/ProductCard";
import { MERREC_BRANDS, MERREC_CATEGORIES, MERREC_PRODUCTS } from "@/lib/merrecData";
import "./products.css";

export default function ProductsPage() {
  return <Suspense fallback={<p style={{ padding: 40 }}>Đang tải sản phẩm…</p>}><ProductListing /></Suspense>;
}
function ProductListing() {
  const params = useSearchParams();
  const [categoryOverride, setCategoryOverride] = useState<string | null>(null);
  const selectedCat = categoryOverride ?? params.get("category") ?? "all";
  const [page, setPage] = useState(1);
  const setSelectedCat = (category: string) => { setCategoryOverride(category); setPage(1); };
  const [selectedBrand, setSelectedBrand] = useState<string>("all");
  const [sortOption, setSortOption] = useState<string>("popular");

  // Filter products based on state
  let filtered = MERREC_PRODUCTS;
  if (selectedCat !== "all") {
    filtered = filtered.filter((p) => p.c0_name.toLowerCase() === selectedCat.toLowerCase());
  }
  if (selectedBrand !== "all") {
    filtered = filtered.filter((p) => p.brand.toLowerCase() === selectedBrand.toLowerCase());
  }

  // Sort products
  if (sortOption === "price-asc") {
    filtered = [...filtered].sort((a, b) => a.price - b.price);
  } else if (sortOption === "price-desc") {
    filtered = [...filtered].sort((a, b) => b.price - a.price);
  }

  return (
    <div className="product-list-wrapper">
      <div className="container-custom">
        {/* Breadcrumb */}
        <div className="breadcrumb">
          <Link href="/">Trang chủ</Link> › <span className="current">Sản phẩm & Danh mục</span>
        </div>

        <div className="listing-grid-layout">
          {/* LEFT SIDEBAR FILTERS */}
          <aside className="filter-sidebar">
            {/* Category Filter */}
            <div>
              <div className="filter-group-title">
                <span>Danh mục sản phẩm</span>
                <span>▾</span>
              </div>
              <ul className="filter-list">
                <li
                  className={`filter-item ${selectedCat === "all" ? "active" : ""}`}
                  onClick={() => setSelectedCat("all")}
                >
                  <span>Tất cả sản phẩm</span>
                  <span className="filter-count">{MERREC_PRODUCTS.length}</span>
                </li>
                {MERREC_CATEGORIES.map((cat) => (
                  <li
                    key={cat.id}
                    className={`filter-item ${selectedCat === cat.c0_name ? "active" : ""}`}
                    onClick={() => setSelectedCat(cat.c0_name)}
                  >
                    <span>{cat.name}</span>
                    <span className="filter-count">{MERREC_PRODUCTS.filter((item) => item.c0_name === cat.c0_name).length}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Brand Filter */}
            <div>
              <div className="filter-group-title">
                <span>Thương hiệu</span>
                <span>▾</span>
              </div>
              <ul className="filter-list">
                <li
                  className={`filter-item ${selectedBrand === "all" ? "active" : ""}`}
                  onClick={() => setSelectedBrand("all")}
                >
                  <span>Tất cả thương hiệu</span>
                </li>
                {MERREC_BRANDS.map((b) => (
                  <li key={b.id} className="filter-item">
                    <label className="checkbox-label" onClick={() => { setSelectedBrand(b.name); setPage(1); }}>
                      <input
                        type="checkbox"
                        checked={selectedBrand === b.name}
                        onChange={() => {}}
                      />
                      <span>{b.name}</span>
                    </label>
                    <span className="filter-count">{b.count}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Price Filter */}
            <div>
              <div className="filter-group-title">
                <span>Khoảng giá</span>
                <span>▾</span>
              </div>
              <ul className="filter-list">
                <li className="filter-item">
                  <label className="checkbox-label">
                    <input type="checkbox" /> Dưới 5.000.000đ
                  </label>
                  <span className="filter-count">120</span>
                </li>
                <li className="filter-item">
                  <label className="checkbox-label">
                    <input type="checkbox" /> 5.000.000đ - 10.000.000đ
                  </label>
                  <span className="filter-count">342</span>
                </li>
                <li className="filter-item">
                  <label className="checkbox-label">
                    <input type="checkbox" /> 10.000.000đ - 15.000.000đ
                  </label>
                  <span className="filter-count">386</span>
                </li>
                <li className="filter-item">
                  <label className="checkbox-label">
                    <input type="checkbox" /> Trên 20.000.000đ
                  </label>
                  <span className="filter-count">162</span>
                </li>
              </ul>

              <div className="price-inputs-row">
                <input type="text" placeholder="Từ đ" className="price-input" />
                <span>-</span>
                <input type="text" placeholder="Đến đ" className="price-input" />
                <button className="apply-price-btn">Áp dụng</button>
              </div>
            </div>

            {/* Star Rating Filter */}
            <div>
              <div className="filter-group-title">
                <span>Đánh giá</span>
                <span>▾</span>
              </div>
              <ul className="filter-list">
                <li className="filter-item">
                  <span className="star-rating-filter">★★★★★ Từ 5 sao</span>
                  <span className="filter-count">892</span>
                </li>
                <li className="filter-item">
                  <span className="star-rating-filter">★★★★☆ Từ 4 sao</span>
                  <span className="filter-count">1.102</span>
                </li>
                <li className="filter-item">
                  <span className="star-rating-filter">★★★☆☆ Từ 3 sao</span>
                  <span className="filter-count">1.210</span>
                </li>
              </ul>
            </div>
          </aside>

          {/* RIGHT MAIN LISTING CONTENT */}
          <main className="main-listing-content">
            {/* Sorting Control Bar */}
            <div className="sorting-bar">
              <div className="sort-left">
                <span className="sort-label">Sắp xếp theo:</span>
                <button
                  className={`sort-btn ${sortOption === "popular" ? "active" : ""}`}
                  onClick={() => setSortOption("popular")}
                >
                  Phổ biến
                </button>
                <button
                  className={`sort-btn ${sortOption === "newest" ? "active" : ""}`}
                  onClick={() => setSortOption("newest")}
                >
                  Mới nhất
                </button>
                <button
                  className={`sort-btn ${sortOption === "price-asc" ? "active" : ""}`}
                  onClick={() => setSortOption("price-asc")}
                >
                  Giá tăng dần
                </button>
                <button
                  className={`sort-btn ${sortOption === "price-desc" ? "active" : ""}`}
                  onClick={() => setSortOption("price-desc")}
                >
                  Giá giảm dần
                </button>
              </div>

              <div className="sort-right">
                <span>Hiển thị: <strong>{Math.min(24, Math.max(0, filtered.length - (page - 1) * 24))} sản phẩm</strong></span>
                <button className="view-mode-btn active">▦</button>
                <button className="view-mode-btn">▤</button>
                <span>Tổng <strong>{filtered.length} sản phẩm</strong></span>
              </div>
            </div>

            {/* Product Grid */}
            <div className="products-grid-4">
              {filtered.slice((page - 1) * 24, page * 24).map((p) => (
                <ProductCard key={p.id} product={p} />
              ))}
            </div>

            {filtered.length === 0 && <p style={{ padding: 30 }}>Chưa có sản phẩm phù hợp với bộ lọc này.</p>}
            <div className="pagination-bar">
              <button className="page-btn" disabled={page <= 1} onClick={() => setPage(page - 1)} aria-label="Trang trước">‹</button>
              {Array.from({ length: Math.ceil(filtered.length / 24) }, (_, index) => <button key={index} className={`page-btn ${page === index + 1 ? "active" : ""}`} onClick={() => setPage(index + 1)}>{index + 1}</button>)}
              <button className="page-btn" disabled={page >= Math.ceil(filtered.length / 24)} onClick={() => setPage(page + 1)} aria-label="Trang sau">›</button>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
