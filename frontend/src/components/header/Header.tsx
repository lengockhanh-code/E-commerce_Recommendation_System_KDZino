"use client";

import { useState, useRef, useEffect } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCart } from "@/lib/cart";
import { useAuth } from "@/lib/auth-context";
import "./Header.css";
import {
  UserIcon,
  CartIcon,
  HeartIcon,
  SearchIcon,
} from "@/components/icons/HeaderIcons";

export default function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const { items } = useCart();
  const { user, login, logout } = useAuth();

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [authPopoverOpen, setAuthPopoverOpen] = useState(false);
  const [emailInput, setEmailInput] = useState("");
  const [passwordInput, setPasswordInput] = useState("");
  const [loginError, setLoginError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    if (typeof window !== "undefined") {
      const q = new URLSearchParams(window.location.search).get("q");
      if (q) setSearchTerm(q);
    }
  }, [pathname]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const query = searchTerm.trim();
    if (query) {
      router.push(`/products?q=${encodeURIComponent(query)}`);
    } else {
      router.push("/products");
    }
  };

  const popoverRef = useRef<HTMLDivElement>(null);
  const totalItems = items.reduce((sum, item) => sum + item.qty, 0);

  // Close auth popover when clicking outside or pressing Escape
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(event.target as Node)) {
        setAuthPopoverOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setAuthPopoverOpen(false);
      }
    };

    if (authPopoverOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("keydown", handleKeyDown);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [authPopoverOpen]);

  const handlePopoverLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError("");
    setIsSubmitting(true);
    try {
      await login(emailInput, passwordInput);
      setAuthPopoverOpen(false);
      setEmailInput("");
      setPasswordInput("");
    } catch (err: any) {
      setLoginError(err.message || "Đăng nhập không thành công.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <header className="header">
      {/* MAIN HEADER - Row 1 */}
      <div className="top-header">
        <Link href="/" className="logo">
          <Image
            src="/kdz_logo.png"
            alt="KDZ"
            width={190}
            height={75}
            priority
            style={{ objectFit: "contain" }}
          />
        </Link>

        {/* SEARCH - Hiện trên Desktop */}
        <form className="search desktop-search" onSubmit={handleSearchSubmit}>
          <input
            type="text"
            aria-label="Tìm kiếm sản phẩm"
            placeholder="Tìm kiếm sản phẩm, thương hiệu, danh mục..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          <button type="submit" className="search-btn" aria-label="Tìm kiếm">
            <SearchIcon />
          </button>
        </form>

        {/* ACTIONS */}
        <div className="actions">
          {/* TÀI KHOẢN (Auth trigger with Popover / Dropdown) */}
          <div
            className="auth-action-wrapper"
            ref={popoverRef}
          >
            <button
              type="button"
              className={`action-item desktop-only-action auth-trigger-btn ${authPopoverOpen ? "active" : ""}`}
              onClick={() => setAuthPopoverOpen(!authPopoverOpen)}
            >
              <span className="icon">
                <UserIcon />
              </span>
              <div className="action-text">
                <p style={{ fontSize: "12px", color: "#444", fontWeight: 400, margin: 0 }}>
                  {user ? "Tài khoản của" : "Đăng nhập / Đăng ký"}
                </p>
                <small style={{ fontSize: "14px", fontWeight: 700, color: "#111" }}>
                  {user ? (user.full_name || user.email.split("@")[0]) : "Tài khoản của tôi"} ▾
                </small>
              </div>
            </button>

            {authPopoverOpen && (
              user ? (
                /* LOGGED IN DROPDOWN MENU - MATCHING USER SCREENSHOT */
                <div className="user-dropdown-menu" onClick={(e) => e.stopPropagation()}>
                  <div className="user-dropdown-arrow" />
                  <div className="user-dropdown-header">
                    <strong>{user.full_name || "Tài khoản của bạn"}</strong>
                    <p>{user.email}</p>
                  </div>
                  <div className="user-dropdown-divider" />
                  <Link href="/profile" className="user-dropdown-item" onClick={() => setAuthPopoverOpen(false)}>
                    Tài khoản của bạn
                  </Link>
                  <Link href="/profile/addresses" className="user-dropdown-item" onClick={() => setAuthPopoverOpen(false)}>
                    Danh sách địa chỉ
                  </Link>
                  <Link href="/profile/history" className="user-dropdown-item" onClick={() => setAuthPopoverOpen(false)}>
                    Lịch sử hoạt động
                  </Link>
                  <div className="user-dropdown-divider" />
                  <button
                    type="button"
                    className="user-dropdown-item logout-btn"
                    onClick={() => {
                      logout();
                      setAuthPopoverOpen(false);
                    }}
                  >
                    Đăng xuất
                  </button>
                </div>
              ) : (
                /* LOGGED OUT POPOVER CARD */
                <div className="auth-popover-card" onClick={(e) => e.stopPropagation()}>
                  <div className="auth-popover-arrow" />
                  <h2 className="auth-popover-title">ĐĂNG NHẬP TÀI KHOẢN</h2>
                  <p className="auth-popover-subtitle">Nhập email và mật khẩu của bạn:</p>

                  {loginError && (
                    <div style={{ color: "#dc2626", fontSize: "12px", textAlign: "center", marginBottom: "10px" }}>
                      {loginError}
                    </div>
                  )}

                  <form className="auth-popover-form" onSubmit={handlePopoverLogin}>
                    <div className="auth-input-group">
                      <input
                        type="text"
                        placeholder="Nhập email hoặc số điện thoại"
                        value={emailInput}
                        onChange={(e) => setEmailInput(e.target.value)}
                        required
                        autoComplete="username"
                      />
                    </div>
                    <div className="auth-input-group">
                      <input
                        type="password"
                        placeholder="Mật khẩu"
                        value={passwordInput}
                        onChange={(e) => setPasswordInput(e.target.value)}
                        required
                        autoComplete="current-password"
                      />
                    </div>

                    <p className="auth-disclaimer">
                      Website được bảo vệ bởi reCAPTCHA và{" "}
                      <Link href="#">Chính sách bảo mật</Link> và{" "}
                      <Link href="#">Điều khoản dịch vụ</Link> của Google.
                    </p>

                    <button type="submit" className="auth-submit-btn" disabled={isSubmitting}>
                      {isSubmitting ? "ĐANG XỬ LÝ..." : "ĐĂNG NHẬP"}
                    </button>
                  </form>

                  <div className="auth-popover-links">
                    <p>
                      Khách hàng mới?{" "}
                      <Link href="/register" onClick={() => setAuthPopoverOpen(false)}>
                        Tạo tài khoản
                      </Link>
                    </p>
                    <p>
                      Quên mật khẩu?{" "}
                      <Link href="#" onClick={() => setAuthPopoverOpen(false)}>
                        Khôi phục mật khẩu
                      </Link>
                    </p>
                  </div>
                </div>
              )
            )}
          </div>

          {/* YÊU THÍCH (WISHLIST) */}
          <Link href="/profile/favorites" className="action-item action-icon-only">
            <span className="icon action-icon-wrapper">
              <HeartIcon />
              <span className="icon-badge">0</span>
            </span>
            <div className="action-text">
              <p>Yêu thích</p>
            </div>
          </Link>

          {/* GIỎ HÀNG */}
          <Link href="/cart" className="action-item action-icon-only" id="header-cart-icon">
            <span className="icon action-icon-wrapper">
              <CartIcon />
              <span className="icon-badge cart-badge">{totalItems}</span>
            </span>
            <div className="action-text">
              <p>Giỏ hàng</p>
              <small>{totalItems} sản phẩm</small>
            </div>
          </Link>
        </div>
      </div>

      {/* MOBILE SECOND ROW */}
      <div className="mobile-search-row">
        <button
          className={`hamburger-btn mobile-hamburger-inline ${mobileMenuOpen ? "active" : ""}`}
          aria-label="Menu"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        >
          <span className="hamburger-icon">
            <span></span>
            <span></span>
            <span></span>
          </span>
        </button>

        <form className="search mobile-search" onSubmit={handleSearchSubmit}>
          <input
            type="text"
            aria-label="Tìm kiếm sản phẩm"
            placeholder="Tìm kiếm sản phẩm, thương hiệu, danh mục..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          <button type="submit" className="search-btn" aria-label="Tìm kiếm">
            <SearchIcon />
          </button>
        </form>
      </div>

      {/* NAVBAR */}
      <nav className="sub-nav">
        <div className="sub-nav-content">
          <div className={`nav-links ${mobileMenuOpen ? "mobile-open" : ""}`}>
            <Link
              href="/"
              className={`nav-link-item ${pathname === "/" ? "active" : ""}`}
              onClick={() => setMobileMenuOpen(false)}
            >
              Trang chủ
            </Link>
            <Link
              href="/products"
              className={`nav-link-item ${pathname === "/products" ? "active" : ""}`}
              onClick={() => setMobileMenuOpen(false)}
            >
              Sản phẩm
            </Link>
            <Link
              href="/mall"
              className={`nav-link-item ${pathname === "/mall" ? "active" : ""}`}
              onClick={() => setMobileMenuOpen(false)}
            >
              KDZino Mall
            </Link>
            <Link
              href="/notifications"
              className={`nav-link-item ${pathname.startsWith("/notifications") ? "active" : ""}`}
              onClick={() => setMobileMenuOpen(false)}
            >
              Thông báo
            </Link>
            <Link
              href="/profile"
              className={`nav-link-item ${pathname.startsWith("/profile") ? "active" : ""}`}
              onClick={() => setMobileMenuOpen(false)}
            >
              Tài Khoản
            </Link>
          </div>
        </div>
      </nav>

      {mobileMenuOpen && (
        <div className="mobile-overlay" onClick={() => setMobileMenuOpen(false)} />
      )}
    </header>
  );
}
