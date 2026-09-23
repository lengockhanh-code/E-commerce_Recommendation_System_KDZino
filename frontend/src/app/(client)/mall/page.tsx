"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import BrandLogo, { mallBrands } from "@/components/mall/BrandLogo";
import { LayoutGrid } from "lucide-react";
import ProductCard from "@/components/productcard/ProductCard";
import { MERREC_PRODUCTS } from "@/lib/merrecData";
import {
  FaTruck,
  FaSyncAlt,
  FaShieldAlt,
  FaHeadset,
  FaCrown
} from "react-icons/fa";
import "./mall.css";

// REAL PRODUCT CATEGORY ICONS MATCHING REFERENCE SCREENSHOT
const mallCategories = [
  {
    name: "Điện thoại",
    image: "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=150&q=80",
  },
  {
    name: "Laptop",
    image: "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=150&q=80",
  },
  {
    name: "Máy tính bảng",
    image: "https://images.unsplash.com/photo-1561154464-82e9adf32764?auto=format&fit=crop&w=150&q=80",
  },
  {
    name: "Đồng hồ",
    image: "https://images.unsplash.com/photo-1508685096489-7aacd43bd3b1?auto=format&fit=crop&w=150&q=80",
  },
  {
    name: "Tai nghe",
    image: "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=150&q=80",
  },
  {
    name: "Phụ kiện",
    image: "https://images.unsplash.com/photo-1583863788434-e58a36330cf0?auto=format&fit=crop&w=150&q=80",
  },
  {
    name: "Gia dụng",
    image: "https://images.unsplash.com/photo-1584269600464-37b1b58a9fe7?auto=format&fit=crop&w=150&q=80",
  },
  {
    name: "Thiết bị thông minh",
    image: "https://images.unsplash.com/photo-1558089687-f282ffcbc126?auto=format&fit=crop&w=150&q=80",
  },
];

const brandStores = [
  {
    name: "Apple",
    slogan: "Think different",
    img: "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=200&q=80",
  },
  {
    name: "SAMSUNG",
    slogan: "Do the Smart Things",
    img: "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?auto=format&fit=crop&w=200&q=80",
  },
  {
    name: "Xiaomi",
    slogan: "Innovation for everyone",
    img: "https://images.unsplash.com/photo-1546054454-aa26e2b734c7?auto=format&fit=crop&w=200&q=80",
  },
  {
    name: "ASUS",
    slogan: "In Search of Incredible",
    img: "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=200&q=80",
  },
];

export default function MallPage() {
  const [timeLeft, setTimeLeft] = useState({ hours: 2, minutes: 15, seconds: 36 });

  // Countdown timer for Flash Sale Mall
  useEffect(() => {
    const timer = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev.seconds > 0) return { ...prev, seconds: prev.seconds - 1 };
        if (prev.minutes > 0) return { ...prev, minutes: 59, seconds: 59 };
        if (prev.hours > 0) return { hours: prev.hours - 1, minutes: 59, seconds: 59 };
        return { hours: 2, minutes: 15, seconds: 0 };
      });
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="mall-page-wrapper">
      <div className="container-custom">
        {/* Breadcrumb */}
        <div className="breadcrumb">
          <Link href="/">Trang chủ</Link> › <span className="current">Mall</span>
        </div>

        {/* 1. TOP MALL BANNER USING /mall1.png FROM PUBLIC */}
        <Link href="/products" className="mall1-top-banner-card">
          <img src="/mall1.png" alt="KDZino Mall Banner" className="mall1-top-banner-img" width={2079} height={756} fetchPriority="high" />
        </Link>

        {/* 2. OFFICIAL BRAND LOGO BAR */}
        <div className="brand-logos-row">
          {mallBrands.map((b) => (
            <Link href="/products" key={b.name} className="brand-logo-card">
              <BrandLogo name={b.name} />
            </Link>
          ))}
          <Link href="/products" className="brand-logo-card brand-more-card">
            <LayoutGrid size={25} aria-hidden="true" /><span>Xem thêm<br />thương hiệu →</span>
          </Link>
        </div>

        {/* 3. TWO-COLUMN MAIN LAYOUT */}
        <div className="mall-main-grid">
          {/* LEFT CONTENT (75%) */}
          <div className="mall-left-content">
            {/* A. MALL CATEGORIES */}
            <div className="mall-cats-box">
              <h3>Danh mục Mall</h3>
              <div className="mall-cats-grid">
                {mallCategories.map((c) => (
                  <Link href="/products" key={c.name} className="mall-cat-item">
                    <div className="mall-cat-img-box">
                      <img src={c.image} alt={c.name} />
                    </div>
                    <span>{c.name}</span>
                  </Link>
                ))}
              </div>
            </div>

            {/* B. FLASH SALE MALL */}
            <div className="flash-sale-mall-card">
              <div className="flash-sale-header">
                <div className="flash-title-group">
                  <span className="flash-main-text">🔥 Flash Sale Mall</span>
                  <div className="timer-box">
                    <span>Kết thúc trong</span>
                    <span className="timer-num">{String(timeLeft.hours).padStart(2, "0")}</span> :
                    <span className="timer-num">{String(timeLeft.minutes).padStart(2, "0")}</span> :
                    <span className="timer-num">{String(timeLeft.seconds).padStart(2, "0")}</span>
                  </div>
                </div>

                <Link href="/products" className="view-all-link">
                  Xem tất cả →
                </Link>
              </div>

              <div className="products-grid-5">
                {MERREC_PRODUCTS.slice(0, 5).map((p) => (
                  <ProductCard key={`flash-mall-${p.id}`} product={p} />
                ))}
              </div>
            </div>

            {/* C. FEATURED BRAND STORES */}
            <div className="brand-stores-section">
              <div className="section-head-flex">
                <h3>Gian hàng thương hiệu nổi bật</h3>
                <Link href="/products" className="view-all-link">
                  Xem tất cả →
                </Link>
              </div>

              <div className="brand-stores-grid">
                {brandStores.map((bs) => (
                  <div key={bs.name} className="brand-store-card">
                    <div>
                      <div className="store-card-header">
                        <BrandLogo name={bs.name} />
                      </div>
                      <div className="store-slogan">{bs.slogan}</div>
                      <Link href="/products" className="store-action-btn">
                        Xem gian hàng →
                      </Link>
                    </div>
                    <img src={bs.img} alt={bs.name} className="store-img-preview" />
                  </div>
                ))}
              </div>
            </div>

            {/* D. BEST SELLERS MALL */}
            <div className="best-sellers-section">
              <div className="section-head-flex">
                <h3>Sản phẩm bán chạy tại Mall</h3>
                <Link href="/products" className="view-all-link">
                  Xem tất cả →
                </Link>
              </div>

              <div className="products-grid-6">
                {MERREC_PRODUCTS.slice(0, 6).map((p) => (
                  <ProductCard key={`best-mall-${p.id}`} product={p} />
                ))}
              </div>
            </div>
          </div>

          {/* RIGHT SIDEBAR (25%) USING /mall2.png FROM PUBLIC */}
          <div className="mall-right-sidebar">
            {/* MALL2.PNG BANNER CARD FROM PUBLIC */}
            <div className="mall2-card-wrapper">
              <img src="/mall2.png" alt="KDZino Mall 2" className="mall2-banner-image" />
            </div>

            {/* MALL BENEFITS CARD */}
            <div className="mall-benefits-card">
              <div className="mall-benefit-row">
                <div className="benefit-icon-circle">
                  <FaTruck />
                </div>
                <div>
                  <div className="benefit-info-title">Giao hàng toàn quốc</div>
                  <div className="benefit-info-sub">Nhanh chóng - An toàn</div>
                </div>
              </div>

              <div className="mall-benefit-row">
                <div className="benefit-icon-circle">
                  <FaSyncAlt />
                </div>
                <div>
                  <div className="benefit-info-title">Đổi trả dễ dàng</div>
                  <div className="benefit-info-sub">Trong 7 ngày</div>
                </div>
              </div>

              <div className="mall-benefit-row">
                <div className="benefit-icon-circle">
                  <FaShieldAlt />
                </div>
                <div>
                  <div className="benefit-info-title">Bảo hành chính hãng</div>
                  <div className="benefit-info-sub">Tại trung tâm ủy quyền</div>
                </div>
              </div>

              <div className="mall-benefit-row">
                <div className="benefit-icon-circle">
                  <FaHeadset />
                </div>
                <div>
                  <div className="benefit-info-title">Hỗ trợ 24/7</div>
                  <div className="benefit-info-sub">Tư vấn tận tâm</div>
                </div>
              </div>
            </div>

            {/* MEMBER PRIVILEGES CARD */}
            <div className="member-privilege-card">
              <div className="crown-icon">
                <FaCrown />
              </div>
              <h4 className="member-title">Ưu đãi dành riêng cho thành viên</h4>
              <p className="member-sub">
                Đăng nhập để nhận nhiều ưu đãi độc quyền tại KDZino Mall
              </p>
              <Link href="/profile" className="member-login-btn">
                Đăng nhập ngay →
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
