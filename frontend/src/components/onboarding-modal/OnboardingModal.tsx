"use client";

import React, { useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { preferencesRequest } from "@/lib/preferences-client";
import { X, Check, Info } from "lucide-react";
import {
  TechGraphic,
  FashionGraphic,
  HomeGraphic,
  BeautyGraphic,
  BabyGraphic,
  SportsGraphic,
  BooksGraphic,
  OtherGraphic,
  HeaderBannerIllustration
} from "./CategoryGraphics";
import "./OnboardingModal.css";

interface OnboardingModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialCategories?: string[];
}

interface CategoryItem {
  id: string;
  title: string;
  desc: string;
  graphic: React.ReactNode;
}

const CATEGORY_ITEMS: CategoryItem[] = [
  {
    id: "tech",
    title: "Điện thoại & Thiết bị số",
    desc: "Điện thoại, laptop, tablet, phụ kiện...",
    graphic: <TechGraphic />
  },
  {
    id: "fashion",
    title: "Thời trang & Phụ kiện",
    desc: "Quần áo, giày dép, túi xách, phụ kiện thời trang...",
    graphic: <FashionGraphic />
  },
  {
    id: "home",
    title: "Nhà cửa & Đời sống",
    desc: "Nội thất, gia dụng, trang trí, đồ dùng sinh hoạt...",
    graphic: <HomeGraphic />
  },
  {
    id: "beauty",
    title: "Mỹ phẩm & Làm đẹp",
    desc: "Chăm sóc da, trang điểm, chăm sóc cá nhân...",
    graphic: <BeautyGraphic />
  },
  {
    id: "baby",
    title: "Đồ chơi & Mẹ Bé",
    desc: "Đồ chơi, đồ dùng cho bé, sản phẩm mẹ & bé...",
    graphic: <BabyGraphic />
  },
  {
    id: "sports",
    title: "Thể thao & Du lịch",
    desc: "Dụng cụ thể thao, phụ kiện outdoor, du lịch...",
    graphic: <SportsGraphic />
  },
  {
    id: "books",
    title: "Sách & Văn phòng phẩm",
    desc: "Sách, truyện, văn phòng phẩm, học tập...",
    graphic: <BooksGraphic />
  },
  {
    id: "other",
    title: "Khác",
    desc: "Các sản phẩm khác",
    graphic: <OtherGraphic />
  }
];

export default function OnboardingModal({ isOpen, onClose, initialCategories = [] }: OnboardingModalProps) {
  const [selectedCategories, setSelectedCategories] = useState<string[]>(initialCategories);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const { token } = useAuth();
  const dialog = useRef<HTMLDialogElement>(null);
  const submitting = useRef(false);
  useEffect(() => {
    if (isOpen && dialog.current && !dialog.current.open) dialog.current.showModal();
  }, [isOpen]);

  if (!isOpen) return null;

  const handleToggleCard = (catId: string) => {
    if (pending) return;
    if (selectedCategories.includes(catId)) {
      setSelectedCategories(selectedCategories.filter((id) => id !== catId));
    } else {
      if (selectedCategories.length < 3) {
        setSelectedCategories([...selectedCategories, catId]);
      }
    }
  };

  const save = async (categories: string[]) => {
    if (!token || submitting.current) return;
    submitting.current = true;
    setPending(true);
    setError("");
    try {
      await preferencesRequest(token, categories);
      const saved = await preferencesRequest(token);
      if (!saved.completed || saved.categories.join(",") !== categories.join(",")) {
        throw new Error("Chưa xác nhận được sở thích đã lưu. Vui lòng thử lại.");
      }
      window.dispatchEvent(new Event("merrec:preferences-changed"));
      onClose();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Chưa lưu được sở thích. Vui lòng thử lại.");
    } finally {
      submitting.current = false;
      setPending(false);
    }
  };
  const handleFinish = () => { if (selectedCategories.length) void save(selectedCategories); };
  const handleSkip = () => { void save([]); };

  return (
    <dialog ref={dialog} className="onboarding-modal-backdrop" aria-labelledby="preferences-title" onCancel={(event) => event.preventDefault()}>
      <div className="onboarding-modal-box" onClick={(e) => e.stopPropagation()}>
        {/* CLOSE BUTTON */}
        <button type="button" className="modal-close-btn" onClick={handleSkip} disabled={pending} aria-label="Bỏ qua chọn sở thích" title="Bỏ qua">
          <X className="w-5 h-5" />
        </button>

        {/* HEADER CONTAINER */}
        <div className="modal-header-container">
          <div className="modal-header-left">
            <div className="modal-accent-bar" />
            <h1 id="preferences-title" className="modal-main-title">Cá nhân hóa trải nghiệm</h1>
            <p className="modal-sub-title-bold">
              Giúp KDZino hiểu bạn hơn để gợi ý đúng sản phẩm phù hợp nhất.
            </p>
            <p className="modal-sub-title-muted">
              Chọn một vài danh mục bạn quan tâm để nhận gợi ý phù hợp. Bạn có thể quay lại trang Sở thích để thay đổi.
            </p>
          </div>

          <div className="modal-header-right-illustration">
            <HeaderBannerIllustration />
          </div>
        </div>

        {/* QUESTION & COUNTER ROW */}
        <div className="modal-question-row">
          <div>
            <h2 className="modal-question-title">Bạn thường quan tâm đến sản phẩm nào?</h2>
            <p className="modal-question-desc">Chọn tối đa 3 danh mục phù hợp nhất với bạn.</p>
          </div>

          <div className="modal-counter-badge">
            Đã chọn: {selectedCategories.length}/3
          </div>
        </div>

        {/* 8 CATEGORIES GRID */}
        <div className="modal-categories-grid">
          {CATEGORY_ITEMS.map((item) => {
            const isSelected = selectedCategories.includes(item.id);
            return (
              <button
                type="button"
                aria-pressed={isSelected}
                disabled={pending || (!isSelected && selectedCategories.length >= 3)}
                key={item.id}
                className={`modal-category-card ${isSelected ? "selected" : ""}`}
                onClick={() => handleToggleCard(item.id)}
              >
                <div className="modal-check-circle">
                  {isSelected && <Check className="w-3.5 h-3.5 stroke-[3]" />}
                </div>

                <div className="modal-card-graphic">{item.graphic}</div>

                <div className="modal-card-content">
                  <div className="modal-card-title">{item.title}</div>
                  <div className="modal-card-desc">{item.desc}</div>
                </div>
              </button>
            );
          })}
        </div>

        {/* BOTTOM ACTIONS BAR */}
        <div className="modal-bottom-bar">
          <div className="modal-info-note">
            <Info className="w-4 h-4 modal-info-icon" />
            <span>Bỏ qua để khám phá sản phẩm phổ biến. Sở thích được lưu theo tài khoản.</span>
          </div>

          <div className="modal-button-group">
            <button type="button" className="btn-modal-skip" onClick={handleSkip} disabled={pending}>
              Bỏ qua
            </button>
            <button type="button" className="btn-modal-submit" onClick={handleFinish} disabled={pending || !selectedCategories.length}>
              {pending ? "Đang lưu…" : "Lưu sở thích"}
            </button>
          </div>
        </div>
        {error && <p role="alert" tabIndex={-1} className="preferences-error">{error}</p>}
      </div>
    </dialog>
  );
}
