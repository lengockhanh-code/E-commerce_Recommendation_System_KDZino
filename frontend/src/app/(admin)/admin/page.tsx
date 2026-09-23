"use client";

import Link from "next/link";
import { MERREC_PRODUCTS, formatPrice } from "@/lib/merrecData";
import "./admin.css";

export default function AdminDashboardPage() {
  return (
    <div className="admin-wrapper">
      {/* SIDEBAR */}
      <aside className="admin-sidebar">
        <div className="admin-brand">
          <span>⚙️</span> KDZino Admin
        </div>

        <ul className="admin-nav">
          <li>
            <Link href="/admin" className="admin-nav-item active">
              📊 Đội ngũ Quản trị
            </Link>
          </li>
          <li>
            <Link href="/products" className="admin-nav-item">
              📦 Quản lý Sản phẩm
            </Link>
          </li>
          <li>
            <Link href="/cart" className="admin-nav-item">
              📑 Quản lý Đơn hàng
            </Link>
          </li>
          <li>
            <Link href="/profile" className="admin-nav-item">
              👥 Khách hàng
            </Link>
          </li>
          <li>
            <Link href="/" className="admin-nav-item">
              🌐 Về Trang Khách hàng
            </Link>
          </li>
        </ul>
      </aside>

      {/* MAIN CONTENT */}
      <main className="admin-main">
        <header className="admin-header">
          <h1 className="admin-title">Bảng điều khiển Quản trị (Admin Dashboard)</h1>
          <span style={{ color: "#64748b", fontSize: "14px" }}>Hệ thống Thương mại Điện tử KDZino</span>
        </header>

        {/* STATS GRID */}
        <div className="admin-stats-grid">
          <div className="stat-card">
            <div className="stat-label">TỔNG SẢN PHẨM</div>
            <div className="stat-val">{MERREC_PRODUCTS.length} SP</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">TỔNG ĐƠN HÀNG</div>
            <div className="stat-val">1.482</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">DOANH THU THÁNG</div>
            <div className="stat-val" style={{ color: "#088751" }}>485.900.000đ</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">KHÁCH HÀNG MỚI</div>
            <div className="stat-val">320</div>
          </div>
        </div>

        {/* RECENT PRODUCTS TABLE */}
        <div className="admin-table-card">
          <h3 style={{ fontSize: "16px", fontWeight: "800", color: "#0f172a" }}>
            Danh sách sản phẩm MerRec Dataset
          </h3>

          <table className="admin-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Tên sản phẩm</th>
                <th>Thương hiệu</th>
                <th>Giá bán</th>
                <th>Giảm giá</th>
                <th>Trạng thái</th>
              </tr>
            </thead>
            <tbody>
              {MERREC_PRODUCTS.map((p) => (
                <tr key={p.id}>
                  <td>#{p.id}</td>
                  <td style={{ fontWeight: "600" }}>{p.name}</td>
                  <td>{p.brand}</td>
                  <td style={{ color: "#ee4d2d", fontWeight: "700" }}>
                    {formatPrice(p.price, p.currency)}
                  </td>
                  <td>-{p.discount}%</td>
                  <td>
                    <span
                      style={{
                        background: "#e2f2e7",
                        color: "#088751",
                        padding: "3px 8px",
                        borderRadius: "4px",
                        fontSize: "11px",
                        fontWeight: "700",
                      }}
                    >
                      Đang kinh doanh
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
