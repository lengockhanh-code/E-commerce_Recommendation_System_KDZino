"use client";

import { useEffect, useState, Suspense } from "react";
import Link from "next/link";

import Banner from "@/components/banner/Banner";
import ProductCard from "@/components/productcard/ProductCard";
import RecommendationStrip from "@/components/recommendation-strip/RecommendationStrip";

import { MERREC_PRODUCTS } from "@/lib/merrecData";
import "../home.css";

function HomeContent() {
  const [activeTab, setActiveTab] = useState("all");
  const [timeLeft, setTimeLeft] = useState({ hours: 12, minutes: 35, seconds: 20 });
  // Countdown timer simulation for Flash Sale
  useEffect(() => {
    const timer = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev.seconds > 0) return { ...prev, seconds: prev.seconds - 1 };
        if (prev.minutes > 0) return { ...prev, minutes: 59, seconds: 59 };
        if (prev.hours > 0) return { hours: prev.hours - 1, minutes: 59, seconds: 59 };
        return { hours: 12, minutes: 0, seconds: 0 };
      });
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Filter products by category tab
  const filteredProducts =
    activeTab === "all"
      ? MERREC_PRODUCTS
      : MERREC_PRODUCTS.filter((p) => p.c0_name.toLowerCase().includes(activeTab.toLowerCase()));

  return (
    <div className="home-wrapper">
      {/* ONBOARDING MODAL POPUP */}


      {/* Hero Section & Category Sidebar & Round Icons & Benefits Strip */}
      <Banner />

      <div className="container-custom">
        {/* FLASH SALE SECTION */}
        <section className="home-section flash-sale-box">
          <div className="section-header">
            <div className="flash-sale-title">
              <span className="flash-icon">⚡</span> FLASH SALE
              <div className="countdown-timer">
                <span className="timer-label">Kết thúc sau</span>
                <span className="timer-unit">{String(timeLeft.hours).padStart(2, "0")}</span>:
                <span className="timer-unit">{String(timeLeft.minutes).padStart(2, "0")}</span>:
                <span className="timer-unit">{String(timeLeft.seconds).padStart(2, "0")}</span>
              </div>
            </div>

            <Link href="/products" className="view-all-link">
              Xem tất cả →
            </Link>
          </div>

          <div className="products-grid-6">
            {MERREC_PRODUCTS.slice(0, 6).map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>
        </section>

        {/* SẢN PHẨM NỔI BẬT SECTION */}
        <section className="home-section">
          <div className="section-header">
            <h2 className="section-main-title">SẢN PHẨM NỔI BẬT</h2>

            <div className="category-tabs">
              <button
                className={`tab-btn ${activeTab === "all" ? "active" : ""}`}
                onClick={() => setActiveTab("all")}
              >
                Tất cả
              </button>
              <button
                className={`tab-btn ${activeTab === "electronics" ? "active" : ""}`}
                onClick={() => setActiveTab("electronics")}
              >
                Điện tử
              </button>
              <button
                className={`tab-btn ${activeTab === "women" ? "active" : ""}`}
                onClick={() => setActiveTab("women")}
              >
                Thời trang Nữ
              </button>
              <button
                className={`tab-btn ${activeTab === "men" ? "active" : ""}`}
                onClick={() => setActiveTab("men")}
              >
                Thời trang Nam
              </button>
              <button
                className={`tab-btn ${activeTab === "beauty" ? "active" : ""}`}
                onClick={() => setActiveTab("beauty")}
              >
                Làm đẹp
              </button>
              <button
                className={`tab-btn ${activeTab === "toys" ? "active" : ""}`}
                onClick={() => setActiveTab("toys")}
              >
                Bộ sưu tập
              </button>
            </div>

            <Link href="/products" className="view-all-link">
              Xem tất cả →
            </Link>
          </div>

          <div className="products-grid-6">
            {filteredProducts.slice(0, 12).map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>
        </section>

        {/* GỢI Ý DÀNH RIÊNG CHO BẠN (MERREC AI RECOMMENDATIONS) SECTION */}
        <RecommendationStrip
          context="home"
          title="✨ Gợi ý dành riêng cho bạn"
          limit={12}
        />
      </div>
    </div>
  );
}

export default function HomePage() {
  return (
    <Suspense fallback={<div className="home-wrapper" />}>
      <HomeContent />
    </Suspense>
  );
}
