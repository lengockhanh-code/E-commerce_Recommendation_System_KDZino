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
  const searchQuery = params.get("q")?.trim() || "";
  const [categoryOverride, setCategoryOverride] = useState<string | null>(null);
  const selectedCat = categoryOverride ?? params.get("category") ?? "all";
  const [page, setPage] = useState(1);
  const setSelectedCat = (category: string) => { setCategoryOverride(category); setPage(1); };
  const [selectedBrand, setSelectedBrand] = useState<string>("all");
  const [selectedPriceRange, setSelectedPriceRange] = useState<string>("all");
  const [minPriceInput, setMinPriceInput] = useState<string>("");
  const [maxPriceInput, setMaxPriceInput] = useState<string>("");
  const [appliedCustomPrice, setAppliedCustomPrice] = useState<{ min?: number; max?: number } | null>(null);

  const [sortOption, setSortOption] = useState<string>("popular");
  const [filterOpen, setFilterOpen] = useState(false);
  const [sortDropdownOpen, setSortDropdownOpen] = useState(false);
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");

  // Count active filters
  let activeFilterCount = 0;
  if (searchQuery) activeFilterCount++;
  if (selectedCat !== "all") activeFilterCount++;
  if (selectedBrand !== "all") activeFilterCount++;
  if (selectedPriceRange !== "all") activeFilterCount++;
  if (appliedCustomPrice) activeFilterCount++;

  // Filter products based on state
  let filtered = MERREC_PRODUCTS;
  if (searchQuery) {
    const term = searchQuery.toLowerCase();
    filtered = filtered.filter(
      (p) =>
        p.name.toLowerCase().includes(term) ||
        p.brand.toLowerCase().includes(term) ||
        p.c0_name.toLowerCase().includes(term) ||
        p.c1_name.toLowerCase().includes(term) ||
        (p.description && p.description.toLowerCase().includes(term))
    );
  }
  if (selectedCat !== "all") {
    filtered = filtered.filter((p) => p.c0_name.toLowerCase() === selectedCat.toLowerCase());
  }
  if (selectedBrand !== "all") {
    filtered = filtered.filter((p) => p.brand.toLowerCase() === selectedBrand.toLowerCase());
  }

  // Filter price range
  if (selectedPriceRange === "under-500k") {
    filtered = filtered.filter((p) => p.price < 500000);
  } else if (selectedPriceRange === "500k-1m") {
    filtered = filtered.filter((p) => p.price >= 500000 && p.price <= 1000000);
  } else if (selectedPriceRange === "1m-2m") {
    filtered = filtered.filter((p) => p.price >= 1000000 && p.price <= 2000000);
  } else if (selectedPriceRange === "above-2m") {
    filtered = filtered.filter((p) => p.price > 2000000);
  }

  if (appliedCustomPrice) {
    const { min, max } = appliedCustomPrice;
    if (min !== undefined) filtered = filtered.filter((p) => p.price >= min);
    if (max !== undefined) filtered = filtered.filter((p) => p.price <= max);
  }

  // Sort products
  if (sortOption === "price-asc") {
    filtered = [...filtered].sort((a, b) => a.price - b.price);
  } else if (sortOption === "price-desc") {
    filtered = [...filtered].sort((a, b) => b.price - a.price);
  }

  const toggleBrand = (brandName: string) => {
    setSelectedBrand((prev) => (prev.toLowerCase() === brandName.toLowerCase() ? "all" : brandName));
    setPage(1);
  };

  const togglePriceRange = (rangeKey: string) => {
    setSelectedPriceRange((prev) => (prev === rangeKey ? "all" : rangeKey));
    setAppliedCustomPrice(null);
    setPage(1);
  };

  const handleApplyCustomPrice = () => {
    const min = minPriceInput ? parseFloat(minPriceInput) : undefined;
    const max = maxPriceInput ? parseFloat(maxPriceInput) : undefined;
    if (min !== undefined || max !== undefined) {
      setSelectedPriceRange("all");
      setAppliedCustomPrice({ min, max });
      setPage(1);
    }
  };

  return (
    <div className="product-list-wrapper">
      <div className="container-custom">
        {/* Breadcrumb */}
        <div className="breadcrumb">
          <Link href="/">Trang chủ</Link> › <span className="current">Sản phẩm</span>
        </div>

        {searchQuery && (
          <div style={{ display: "flex", alignItems: "center", gap: "8px", margin: "10px 0 15px", padding: "10px 14px", background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: "8px", color: "#166534" }}>
            <span>Kết quả tìm kiếm cho: <strong>"{searchQuery}"</strong></span>
            <Link href="/products" style={{ marginLeft: "auto", fontSize: "13px", color: "#dc2626", textDecoration: "underline", fontWeight: 600 }}>
              ✕ Xóa tìm kiếm
            </Link>
          </div>
        )}

        {/* TOP TOOLBAR FOR MOBILE & TABLET */}
        <div className="products-responsive-toolbar">
          <div className="toolbar-left-btns">
            {/* 1. Filter Pill Button */}
            <button
              className="toolbar-btn filter-pill-btn"
              onClick={() => setFilterOpen(true)}
            >
              <span className="btn-icon">🎛️</span>
              <span>Bộ lọc</span>
              {activeFilterCount > 0 && <span className="pill-count">({activeFilterCount})</span>}
            </button>

            {/* 2. Sort Pill Button with Dropdown */}
            <div className="sort-popover-wrapper">
              <button
                className="toolbar-btn sort-pill-btn"
                onClick={() => setSortDropdownOpen(!sortDropdownOpen)}
              >
                <span className="btn-icon">⇅</span>
                <span>Sắp xếp</span>
              </button>

              {sortDropdownOpen && (
                <div className="sort-dropdown-menu">
                  <button
                    className={sortOption === "popular" ? "active" : ""}
                    onClick={() => { setSortOption("popular"); setSortDropdownOpen(false); }}
                  >
                    Phổ biến
                  </button>
                  <button
                    className={sortOption === "newest" ? "active" : ""}
                    onClick={() => { setSortOption("newest"); setSortDropdownOpen(false); }}
                  >
                    Mới nhất
                  </button>
                  <button
                    className={sortOption === "price-asc" ? "active" : ""}
                    onClick={() => { setSortOption("price-asc"); setSortDropdownOpen(false); }}
                  >
                    Giá tăng dần
                  </button>
                  <button
                    className={sortOption === "price-desc" ? "active" : ""}
                    onClick={() => { setSortOption("price-desc"); setSortDropdownOpen(false); }}
                  >
                    Giá giảm dần
                  </button>
                </div>
              )}
            </div>

            {/* 3. View mode toggle */}
            <div className="toolbar-view-toggle">
              <button
                className={`view-btn ${viewMode === "grid" ? "active" : ""}`}
                onClick={() => setViewMode("grid")}
                title="Lưới"
              >
                ▦
              </button>
              <button
                className={`view-btn ${viewMode === "list" ? "active" : ""}`}
                onClick={() => setViewMode("list")}
                title="Danh sách"
              >
                ▤
              </button>
            </div>
          </div>

          {/* 4. Total count text */}
          <div className="toolbar-total-text">
            Tổng <strong>{filtered.length}</strong> sản phẩm
          </div>
        </div>

        <div className="listing-grid-layout">
          {/* LEFT SIDEBAR FILTERS */}
          <aside className={`filter-sidebar ${filterOpen ? "mobile-open" : ""}`}>
            {/* Mobile close button */}
            <div className="filter-sidebar-header">
              <h3>Bộ lọc sản phẩm</h3>
              <button
                className="filter-close-btn"
                onClick={() => setFilterOpen(false)}
              >
                ✕ Đóng
              </button>
            </div>

            {/* Category Filter */}
            <div>
              <div className="filter-group-title">
                <span>Danh mục sản phẩm</span>
                <span>▾</span>
              </div>
              <ul className="filter-list">
                <li
                  className={`filter-item ${selectedCat === "all" ? "active" : ""}`}
                  onClick={() => { setSelectedCat("all"); setFilterOpen(false); }}
                >
                  <span>Tất cả sản phẩm</span>
                  <span className="filter-count">30.044.422</span>
                </li>
                {MERREC_CATEGORIES.map((cat) => (
                  <li
                    key={cat.id}
                    className={`filter-item ${selectedCat === cat.c0_name ? "active" : ""}`}
                    onClick={() => { setSelectedCat(cat.c0_name); setFilterOpen(false); }}
                  >
                    <span>{cat.name}</span>
                    <span className="filter-count">{cat.count.toLocaleString("vi-VN")}</span>
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
                    <label className="checkbox-label" onClick={() => toggleBrand(b.name)}>
                      <input
                        type="checkbox"
                        checked={selectedBrand.toLowerCase() === b.name.toLowerCase()}
                        onChange={() => {}}
                      />
                      <span>{b.name}</span>
                    </label>
                    <span className="filter-count">{b.count.toLocaleString("vi-VN")}</span>
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
                {[
                  { key: "under-500k", label: "Dưới 500.000đ", count: 10678586 },
                  { key: "500k-1m", label: "500.000đ - 1.000.000đ", count: 9254148 },
                  { key: "1m-2m", label: "1.000.000đ - 2.000.000đ", count: 5427004 },
                  { key: "above-2m", label: "Trên 2.000.000đ", count: 4684684 },
                ].map((range) => (
                  <li key={range.key} className="filter-item">
                    <label className="checkbox-label" onClick={() => togglePriceRange(range.key)}>
                      <input
                        type="checkbox"
                        checked={selectedPriceRange === range.key}
                        onChange={() => {}}
                      />
                      <span>{range.label}</span>
                    </label>
                    <span className="filter-count">{range.count.toLocaleString("vi-VN")}</span>
                  </li>
                ))}
              </ul>

              <div className="price-inputs-row">
                <input
                  type="number"
                  placeholder="Từ đ"
                  className="price-input"
                  value={minPriceInput}
                  onChange={(e) => setMinPriceInput(e.target.value)}
                />
                <span>-</span>
                <input
                  type="number"
                  placeholder="Đến đ"
                  className="price-input"
                  value={maxPriceInput}
                  onChange={(e) => setMaxPriceInput(e.target.value)}
                />
                <button type="button" className="apply-price-btn" onClick={handleApplyCustomPrice}>
                  Áp dụng
                </button>
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
                  <span className="filter-count">8.920.400</span>
                </li>
                <li className="filter-item">
                  <span className="star-rating-filter">★★★★☆ Từ 4 sao</span>
                  <span className="filter-count">11.020.150</span>
                </li>
                <li className="filter-item">
                  <span className="star-rating-filter">★★★☆☆ Từ 3 sao</span>
                  <span className="filter-count">12.100.800</span>
                </li>
              </ul>
            </div>
          </aside>

          {/* Mobile filter overlay */}
          {filterOpen && (
            <div className="filter-overlay" onClick={() => setFilterOpen(false)} />
          )}

          {/* RIGHT MAIN LISTING CONTENT */}
          <main className="main-listing-content">
            {/* Desktop Sorting Bar */}
            <div className="sorting-bar desktop-only-sorting-bar">
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
                <span>Tổng <strong>{filtered.length} sản phẩm</strong></span>
              </div>
            </div>

            {/* Product Grid */}
            <div className={`products-grid-4 ${viewMode === "list" ? "list-mode-grid" : ""}`}>
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
