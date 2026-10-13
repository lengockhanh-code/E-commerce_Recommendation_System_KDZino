"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  Package,
  ClipboardList,
  Warehouse,
  Tag,
  Users,
  BadgeDollarSign,
  BarChart3,
  MessageSquare,
  Settings,
  HelpCircle,
  Bell,
  Search,
  ChevronDown,
  ChevronRight,
  Store,
  ExternalLink,
  PlusCircle,
  ListFilter
} from "lucide-react";
import "./seller.css";
import { useAuth } from "@/lib/auth-context";

export default function SellerLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user } = useAuth();

  const [productsOpen, setProductsOpen] = useState(true);
  const [ordersOpen, setOrdersOpen] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      router.push(`/seller/products?q=${encodeURIComponent(searchQuery.trim())}`);
    }
  };

  const shopName = user?.full_name ? `Shop ${user.full_name}` : "Shop KDZino Official";

  return (
    <div className="seller-wrapper">
      {/* SELLER HEADER */}
      <header className="seller-header">
        <div className="seller-header-left">
          <Link href="/seller" className="seller-brand-link">
            <Image
              src="/kdz_logo.png"
              alt="KDZino"
              width={140}
              height={44}
              priority
              style={{ objectFit: "contain" }}
            />
            <div className="seller-brand-text">
              <span className="seller-portal-title">Kênh Người Bán</span>
              <span className="seller-portal-subtitle">Bán dễ dàng - Tăng trưởng cùng MerRec</span>
            </div>
          </Link>
        </div>

        {/* SEARCH BAR */}
        <form className="seller-header-search" onSubmit={handleSearch}>
          <input
            type="text"
            placeholder="Tìm kiếm tính năng, đơn hàng, sản phẩm..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <button type="submit" className="seller-header-search-btn" aria-label="Tìm kiếm">
            <Search size={16} />
          </button>
        </form>

        {/* RIGHT ACTIONS */}
        <div className="seller-header-right">
          <button type="button" className="seller-icon-btn" title="Tin nhắn">
            <MessageSquare size={19} />
            <span className="seller-badge-count">3</span>
            <span>Tin nhắn</span>
          </button>

          <button type="button" className="seller-icon-btn" title="Thông báo">
            <Bell size={19} />
            <span className="seller-badge-count">12</span>
            <span>Thông báo</span>
          </button>

          <div className="seller-shop-profile" title="Tài khoản người bán">
            <div className="seller-shop-avatar">
              <Store size={20} />
            </div>
            <div className="seller-shop-info">
              <span className="seller-shop-name">{shopName}</span>
              <span className="seller-shop-role">Người bán</span>
            </div>
          </div>
        </div>
      </header>

      {/* SELLER SIDEBAR */}
      <aside className="seller-sidebar">
        <div className="seller-sidebar-group">
          {/* TỔNG QUAN */}
          <Link
            href="/seller"
            className={`seller-sidebar-item ${pathname === "/seller" ? "active" : ""}`}
          >
            <div className="seller-sidebar-item-left">
              <LayoutDashboard size={18} />
              <span>Tổng quan</span>
            </div>
          </Link>

          {/* QUẢN LÝ SẢN PHẨM */}
          <button
            type="button"
            className={`seller-sidebar-item ${pathname.startsWith("/seller/products") ? "active" : ""}`}
            onClick={() => setProductsOpen(!productsOpen)}
          >
            <div className="seller-sidebar-item-left">
              <Package size={18} />
              <span>Quản lý sản phẩm</span>
            </div>
            {productsOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          </button>
          {productsOpen && (
            <div className="seller-sub-items">
              <Link
                href="/seller/products"
                className={`seller-sub-item ${pathname === "/seller/products" ? "active" : ""}`}
              >
                <span>Danh sách sản phẩm</span>
              </Link>
              <Link
                href="/seller/products/new"
                className={`seller-sub-item ${pathname === "/seller/products/new" ? "active" : ""}`}
              >
                <span>Thêm sản phẩm</span>
              </Link>
              <Link
                href="/seller/products?tab=categories"
                className={`seller-sub-item ${pathname === "/seller/products?tab=categories" ? "active" : ""}`}
              >
                <span>Quản lý danh mục</span>
              </Link>
              <Link
                href="/seller/products?tab=brands"
                className={`seller-sub-item ${pathname === "/seller/products?tab=brands" ? "active" : ""}`}
              >
                <span>Quản lý thương hiệu</span>
              </Link>
            </div>
          )}

          {/* QUẢN LÝ ĐƠN HÀNG */}
          <button
            type="button"
            className={`seller-sidebar-item ${pathname.startsWith("/seller/orders") ? "active" : ""}`}
            onClick={() => setOrdersOpen(!ordersOpen)}
          >
            <div className="seller-sidebar-item-left">
              <ClipboardList size={18} />
              <span>Quản lý đơn hàng</span>
            </div>
            {ordersOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          </button>
          {ordersOpen && (
            <div className="seller-sub-items">
              <Link
                href="/seller/orders"
                className={`seller-sub-item ${pathname === "/seller/orders" ? "active" : ""}`}
              >
                <span>Tất cả đơn hàng</span>
              </Link>
              <Link
                href="/seller/orders?status=pending"
                className="seller-sub-item"
              >
                <span>Chờ xác nhận</span>
                <span className="seller-badge-pill">12</span>
              </Link>
              <Link
                href="/seller/orders?status=confirmed"
                className="seller-sub-item"
              >
                <span>Chờ lấy hàng</span>
                <span className="seller-badge-pill" style={{ background: "#e11d48" }}>8</span>
              </Link>
              <Link
                href="/seller/orders?status=shipping"
                className="seller-sub-item"
              >
                <span>Đang giao</span>
              </Link>
              <Link
                href="/seller/orders?status=completed"
                className="seller-sub-item"
              >
                <span>Hoàn thành</span>
              </Link>
              <Link
                href="/seller/orders?status=cancelled"
                className="seller-sub-item"
              >
                <span>Đã hủy / Trả hàng</span>
              </Link>
            </div>
          )}

          {/* QUẢN LÝ KHO */}
          <Link href="/seller/products" className="seller-sidebar-item">
            <div className="seller-sidebar-item-left">
              <Warehouse size={18} />
              <span>Quản lý kho</span>
            </div>
          </Link>

          {/* KHUYẾN MÃI */}
          <Link href="/seller" className="seller-sidebar-item">
            <div className="seller-sidebar-item-left">
              <Tag size={18} />
              <span>Khuyến mãi</span>
            </div>
          </Link>

          {/* KHÁCH HÀNG */}
          <Link href="/seller" className="seller-sidebar-item">
            <div className="seller-sidebar-item-left">
              <Users size={18} />
              <span>Khách hàng</span>
            </div>
          </Link>

          {/* DOANH THU & TÀI CHÍNH */}
          <Link href="/seller" className="seller-sidebar-item">
            <div className="seller-sidebar-item-left">
              <BadgeDollarSign size={18} />
              <span>Doanh thu & Tài chính</span>
            </div>
          </Link>

          {/* PHÂN TÍCH */}
          <Link href="/seller" className="seller-sidebar-item">
            <div className="seller-sidebar-item-left">
              <BarChart3 size={18} />
              <span>Phân tích</span>
            </div>
          </Link>

          {/* CHAT VỚI KHÁCH HÀNG */}
          <Link href="/seller" className="seller-sidebar-item">
            <div className="seller-sidebar-item-left">
              <MessageSquare size={18} />
              <span>Chat với khách hàng</span>
            </div>
          </Link>

          {/* THIẾT LẬP SHOP */}
          <Link href="/seller" className="seller-sidebar-item">
            <div className="seller-sidebar-item-left">
              <Settings size={18} />
              <span>Thiết lập Shop</span>
            </div>
          </Link>

          {/* TRUNG TÂM HỖ TRỢ */}
          <Link href="/seller" className="seller-sidebar-item">
            <div className="seller-sidebar-item-left">
              <HelpCircle size={18} />
              <span>Trung tâm hỗ trợ</span>
            </div>
          </Link>

          <div style={{ height: "1px", background: "#e5e7eb", margin: "16px 8px" }} />

          {/* QUAY LẠI TRANG MUA SẮM */}
          <Link
            href="/"
            className="seller-sidebar-item"
            style={{ color: "#008848", fontWeight: 600, background: "#f0fbf5" }}
          >
            <div className="seller-sidebar-item-left">
              <ExternalLink size={18} />
              <span>Về sàn mua sắm KDZino</span>
            </div>
          </Link>
        </div>
      </aside>

      {/* MAIN VIEW */}
      <main className="seller-main">{children}</main>
    </div>
  );
}
