"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import CategoryStrip from "@/components/category-strip/CategoryStrip";
import BenefitsStrip from "@/components/benefits-strip/BenefitsStrip";
import {
  ShirtIcon,
  PhoneIcon,
  LaptopIcon,
  ClockIcon,
  BeautyIcon,
  HomeIcon,
  SportIcon,
  BabyIcon,
  CarIcon,
  BookIcon,
  FoodIcon
} from "@/components/icons/CategoryIcons";
import "./Banner.css";

const rawBanners = [
  "/banner1.png",
  "/banner2.png",
  "/banner3.png",
  "/banner4.png",
  "/banner5.png",
];

const extendedBanners = rawBanners;

const sidebarMenuItems = [
  { icon: <ShirtIcon />, name: "Thời trang & Phụ kiện" },
  { icon: <PhoneIcon />, name: "Điện thoại & Thiết bị số" },
  { icon: <LaptopIcon />, name: "Máy tính & Laptop" },
  { icon: <ClockIcon />, name: "Điện tử & Gia dụng" },
  { icon: <BeautyIcon />, name: "Sức khỏe & Làm đẹp" },
  { icon: <HomeIcon />, name: "Nhà cửa & Đời sống" },
  { icon: <SportIcon />, name: "Thể thao & Du lịch" },
  { icon: <BabyIcon />, name: "Đồ chơi & Mẹ & Bé" },
  { icon: <CarIcon />, name: "Ô tô & Xe máy" },
  { icon: <BookIcon />, name: "Sách & Văn phòng phẩm" },
  { icon: <FoodIcon />, name: "Thực phẩm & Đồ uống" },
];

interface BannerProps {
  showSidebar?: boolean;
}

export default function Banner({ showSidebar = true }: BannerProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [withTransition, setWithTransition] = useState(true);

  // Auto slide smoothly right every 3.5s
  useEffect(() => {
    const interval = setInterval(() => {
      setWithTransition(true);
      setCurrentIndex((prev) => (prev + 1) % rawBanners.length);
    }, 3500);
    return () => clearInterval(interval);
  }, [currentIndex]);

  const handleNext = () => {
    setWithTransition(true);
    setCurrentIndex((prev) => (prev + 1) % rawBanners.length);
  };

  const handlePrev = () => {
    setWithTransition(true);
    setCurrentIndex((prev) => (prev - 1 + rawBanners.length) % rawBanners.length);
  };

  const handleTransitionEnd = () => {};

  const activeDotIndex = currentIndex % rawBanners.length;

  return (
    <section className="banner-section">
      <div className="container-custom">
        {/* HERO GRID: SIDEBAR & CAROUSEL */}
        <div className={`hero-layout-grid ${!showSidebar ? "no-sidebar" : ""}`}>
          {/* 1. SIDEBAR TRÁI HOÀN CHỈNH UNIFIED CARD */}
          {showSidebar && (
            <div className="category-sidebar-unified">
              <div className="sidebar-header-green">
                <span>☰</span> Danh mục sản phẩm
              </div>

              <div className="sidebar-body-list">
                {sidebarMenuItems.map((item) => (
                  <Link href="/products" key={item.name} className="sidebar-menu-item">
                    <div className="menu-item-left">
                      <span className="menu-icon">{item.icon}</span>
                      <span>{item.name}</span>
                    </div>
                    <span className="arrow-right-icon">›</span>
                  </Link>
                ))}
                <div className="more-categories-item">
                  <span>›</span>
                  <span>Xem thêm danh mục</span>
                </div>
              </div>
            </div>
          )}

          {/* 2. CAROUSEL BANNER TRƯỢT SANG PHẢI VÔ TẬN & KHÔNG CẮT ẢNH */}
          <div className="banner-carousel-container">
            <div className="carousel-track-wrapper">
              <div
                className="carousel-slides-track"
                style={{
                  transform: `translateX(-${currentIndex * 100}%)`,
                  transition: withTransition ? "transform 0.5s ease-in-out" : "none",
                }}
                onTransitionEnd={handleTransitionEnd}
              >
                {extendedBanners.map((banner, index) => (
                  <div className="carousel-slide-item" key={index}>
                    <img src={banner} alt={`Banner ${(index % rawBanners.length) + 1}`} />
                  </div>
                ))}
              </div>
            </div>

            {/* CÂN ĐỐI NÚT ĐIỀU HƯỚNG TRÁI / PHẢI CHUẨN ĐẸP VỚI SVG */}
            <button
              className="carousel-nav-btn prev-btn"
              onClick={handlePrev}
              title="Xem ảnh trước"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="15 18 9 12 15 6"></polyline>
              </svg>
            </button>

            <button
              className="carousel-nav-btn next-btn"
              onClick={handleNext}
              title="Xem ảnh tiếp theo"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </button>

            {/* DOTS */}
            <div className="carousel-dots-row">
              {rawBanners.map((_, idx) => (
                <button
                  key={idx}
                  className={`carousel-dot-item ${idx === activeDotIndex ? "active" : ""}`}
                  onClick={() => {
                    setWithTransition(true);
                    setCurrentIndex(idx);
                  }}
                />
              ))}
            </div>
          </div>
        </div>

        {/* 3. HÀNG ICON DANH MỤC TRÒN VỚI ẢNH THẬT */}
        <CategoryStrip />

        {/* 4. THANH MÂU XANH MỊN (#009643) WITH GREEN SVG ICONS (SEPARATE COMPONENT) */}
        <BenefitsStrip />
      </div>
    </section>
  );
}
