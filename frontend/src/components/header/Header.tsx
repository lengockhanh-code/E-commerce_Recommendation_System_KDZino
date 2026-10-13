"use client";

import { useState, useRef, useEffect } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCart } from "@/lib/cart";
import { useAuth } from "@/lib/auth-context";
import { formatPrice } from "@/lib/merrecData";
import { MessageSquare } from "lucide-react";
import "./Header.css";
import {
  UserIcon,
  CartIcon,
  HeartIcon,
  SearchIcon,
} from "@/components/icons/HeaderIcons";

interface SearchSuggestionProduct {
  id: string;
  name: string;
  price: number;
  originalPrice?: number;
  image: string;
  category: string;
  brand: string;
}

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

  // Live search state
  const [searchResults, setSearchResults] = useState<SearchSuggestionProduct[]>([]);
  const [searchCategories, setSearchCategories] = useState<string[]>([]);
  const [searchTotal, setSearchTotal] = useState(0);
  const [searchDropdownOpen, setSearchDropdownOpen] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const searchContainerRef = useRef<HTMLDivElement>(null);
  const mobileSearchContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const q = new URLSearchParams(window.location.search).get("q");
      if (q) setSearchTerm(q);
    }
  }, [pathname]);

  // Debounced live search autocomplete
  useEffect(() => {
    const query = searchTerm.trim();
    if (!query) {
      setSearchResults([]);
      setSearchCategories([]);
      setSearchTotal(0);
      setSearchDropdownOpen(false);
      return;
    }

    setIsSearching(true);
    const timer = setTimeout(() => {
      fetch(`/api/search?q=${encodeURIComponent(query)}`)
        .then((res) => {
          if (!res.ok) throw new Error("Search failed");
          return res.json();
        })
        .then((data) => {
          setSearchResults(data.products || []);
          setSearchCategories(data.categories || []);
          setSearchTotal(data.total || 0);
          setSearchDropdownOpen(true);
        })
        .catch((err) => {
          console.warn("Live search error:", err);
        })
        .finally(() => {
          setIsSearching(false);
        });
    }, 150);

    return () => clearTimeout(timer);
  }, [searchTerm]);

  // Click outside to close live search dropdown
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (
        searchContainerRef.current &&
        !searchContainerRef.current.contains(target) &&
        (!mobileSearchContainerRef.current || !mobileSearchContainerRef.current.contains(target))
      ) {
        setSearchDropdownOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setSearchDropdownOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  const handleSearchSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setSearchDropdownOpen(false);
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

  if (pathname.startsWith("/seller")) {
    return null;
  }

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
        <div className="search-container desktop-search-container" ref={searchContainerRef}>
          <form className="search desktop-search" onSubmit={handleSearchSubmit}>
            <input
              type="text"
              aria-label="Tìm kiếm sản phẩm"
              placeholder="Tìm kiếm sản phẩm, thương hiệu, danh mục..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                if (e.target.value.trim()) setSearchDropdownOpen(true);
              }}
              onFocus={() => {
                if (searchTerm.trim()) setSearchDropdownOpen(true);
              }}
            />
            <button type="submit" className="search-btn" aria-label="Tìm kiếm">
              <SearchIcon />
            </button>
          </form>

          {/* AUTOCOMPLETE DROPDOWN */}
          {searchDropdownOpen && searchTerm.trim() && (
            <div className="search-dropdown" onClick={(e) => e.stopPropagation()}>
              <div className="search-dropdown-header">
                <span>
                  Gợi ý cho &quot;<strong>{searchTerm}</strong>&quot;
                </span>
                {isSearching ? (
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <span className="search-spinner" />
                    <span>Đang tìm...</span>
                  </div>
                ) : (
                  <span>{searchTotal} kết quả</span>
                )}
              </div>

              {isSearching && searchResults.length === 0 ? (
                <div className="search-dropdown-loading">
                  <span className="search-spinner" />
                  <span>Đang tìm kiếm sản phẩm...</span>
                </div>
              ) : searchResults.length === 0 ? (
                <div className="search-dropdown-empty">
                  Không tìm thấy sản phẩm phù hợp với &quot;{searchTerm}&quot;.
                  <br />
                  <small style={{ color: "#9ca3af", marginTop: "4px", display: "inline-block" }}>
                    Thử tìm với từ khóa khác (áo, giày, sách, balo, tai nghe...)
                  </small>
                </div>
              ) : (
                <>
                  <div className="search-dropdown-list">
                    {searchResults.map((product) => (
                      <Link
                        key={product.id}
                        href={`/products/${product.id}`}
                        className="search-dropdown-item"
                        onClick={() => setSearchDropdownOpen(false)}
                      >
                        <img
                          src={product.image || "/placeholder.svg"}
                          alt={product.name}
                          className="search-dropdown-img"
                        />
                        <div className="search-dropdown-info">
                          <div className="search-dropdown-name">{product.name}</div>
                          <div className="search-dropdown-meta">
                            <span className="search-dropdown-cat-badge">{product.category}</span>
                            {product.brand && <span>• {product.brand}</span>}
                          </div>
                        </div>
                        <div className="search-dropdown-price">
                          {formatPrice(product.price)}
                        </div>
                      </Link>
                    ))}
                  </div>

                  {searchCategories.length > 0 && (
                    <div className="search-dropdown-categories">
                      <span style={{ fontSize: "11.5px", color: "#64748b" }}>Danh mục gợi ý:</span>
                      {searchCategories.map((cat) => (
                        <button
                          key={cat}
                          type="button"
                          className="search-dropdown-cat-chip"
                          onClick={() => {
                            setSearchDropdownOpen(false);
                            router.push(`/products?q=${encodeURIComponent(searchTerm.trim())}&category=${encodeURIComponent(cat)}`);
                          }}
                        >
                          🔍 {cat}
                        </button>
                      ))}
                    </div>
                  )}

                  <div className="search-dropdown-footer">
                    <button
                      type="button"
                      className="search-dropdown-footer-btn"
                      onClick={() => handleSearchSubmit()}
                    >
                      Xem tất cả {searchTotal > 0 ? `${searchTotal} ` : ""}kết quả cho &quot;{searchTerm}&quot; →
                    </button>
                  </div>
                </>
              )}
            </div>
          )}
        </div>

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

          {/* TIN NHẮN (CHAT) */}
          <Link href="/chat" className="action-item action-icon-only" title="Tin nhắn">
            <span className="icon action-icon-wrapper">
              <MessageSquare size={22} color="#088751" />
              <span className="icon-badge">2</span>
            </span>
            <div className="action-text">
              <p>Tin nhắn</p>
            </div>
          </Link>

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

        <div className="search-container mobile-search-container" ref={mobileSearchContainerRef}>
          <form className="search mobile-search" onSubmit={handleSearchSubmit}>
            <input
              type="text"
              aria-label="Tìm kiếm sản phẩm"
              placeholder="Tìm kiếm sản phẩm, thương hiệu, danh mục..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                if (e.target.value.trim()) setSearchDropdownOpen(true);
              }}
              onFocus={() => {
                if (searchTerm.trim()) setSearchDropdownOpen(true);
              }}
            />
            <button type="submit" className="search-btn" aria-label="Tìm kiếm">
              <SearchIcon />
            </button>
          </form>

          {/* MOBILE AUTOCOMPLETE DROPDOWN */}
          {searchDropdownOpen && searchTerm.trim() && (
            <div className="search-dropdown" onClick={(e) => e.stopPropagation()}>
              <div className="search-dropdown-header">
                <span>
                  Gợi ý cho &quot;<strong>{searchTerm}</strong>&quot;
                </span>
                {isSearching ? (
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <span className="search-spinner" />
                    <span>Đang tìm...</span>
                  </div>
                ) : (
                  <span>{searchTotal} kết quả</span>
                )}
              </div>

              {isSearching && searchResults.length === 0 ? (
                <div className="search-dropdown-loading">
                  <span className="search-spinner" />
                  <span>Đang tìm kiếm...</span>
                </div>
              ) : searchResults.length === 0 ? (
                <div className="search-dropdown-empty">
                  Không tìm thấy sản phẩm cho &quot;{searchTerm}&quot;.
                </div>
              ) : (
                <>
                  <div className="search-dropdown-list">
                    {searchResults.map((product) => (
                      <Link
                        key={product.id}
                        href={`/products/${product.id}`}
                        className="search-dropdown-item"
                        onClick={() => setSearchDropdownOpen(false)}
                      >
                        <img
                          src={product.image || "/placeholder.svg"}
                          alt={product.name}
                          className="search-dropdown-img"
                        />
                        <div className="search-dropdown-info">
                          <div className="search-dropdown-name">{product.name}</div>
                          <div className="search-dropdown-meta">
                            <span className="search-dropdown-cat-badge">{product.category}</span>
                          </div>
                        </div>
                        <div className="search-dropdown-price">
                          {formatPrice(product.price)}
                        </div>
                      </Link>
                    ))}
                  </div>

                  <div className="search-dropdown-footer">
                    <button
                      type="button"
                      className="search-dropdown-footer-btn"
                      onClick={() => handleSearchSubmit()}
                    >
                      Xem tất cả kết quả →
                    </button>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
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
