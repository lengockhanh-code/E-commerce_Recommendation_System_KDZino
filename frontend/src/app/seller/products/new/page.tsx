"use client";

import { useState, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  UploadCloud,
  X,
  Plus,
  Truck,
  Bold,
  Italic,
  Underline,
  List,
  ListOrdered,
  AlignLeft,
  Link as LinkIcon,
  Image as ImageIcon,
  CheckCircle,
  AlertCircle
} from "lucide-react";

const SAMPLE_DEFAULT_IMAGES = [
  "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=400&auto=format&fit=crop&q=80",
  "https://images.unsplash.com/photo-1525966222134-fcfa99b8ae77?w=400&auto=format&fit=crop&q=80",
  "https://images.unsplash.com/photo-1560769629-975ec94e6a86?w=400&auto=format&fit=crop&q=80",
  "https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a?w=400&auto=format&fit=crop&q=80",
];

export default function NewProductPage() {
  const router = useRouter();

  // Images state
  const [images, setImages] = useState<string[]>(SAMPLE_DEFAULT_IMAGES);
  const [newImageUrl, setNewImageUrl] = useState("");
  const [showUrlInput, setShowUrlInput] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Form fields
  const [name, setName] = useState("");
  const [category0, setCategory0] = useState("Thời trang");
  const [brand, setBrand] = useState("");
  const [shortDesc, setShortDesc] = useState("");
  const [description, setDescription] = useState("");

  // Pricing
  const [originalPrice, setOriginalPrice] = useState<number | "">(0);
  const [price, setPrice] = useState<number | "">(0);
  const [promoEnabled, setPromoEnabled] = useState(false);
  const [promoPrice, setPromoPrice] = useState<number | "">(0);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  // Inventory & shipping
  const [stock, setStock] = useState<number | "">(100);
  const [sku, setSku] = useState("");
  const [weight, setWeight] = useState<number | "">(350);
  const [length, setLength] = useState("");
  const [width, setWidth] = useState("");
  const [height, setHeight] = useState("");
  const [shipper, setShipper] = useState("MerRec Express");

  // Variant attributes
  const [variants, setVariants] = useState<string[]>(["Màu sắc (Trắng, Đen)", "Size (39, 40, 41, 42)"]);
  const [newVariant, setNewVariant] = useState("");

  // Submission state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successToast, setSuccessToast] = useState(false);

  // Handle local file selection
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      const reader = new FileReader();
      reader.onload = (uploadEvent) => {
        if (uploadEvent.target?.result) {
          setImages((prev) => [...prev, String(uploadEvent.target?.result)].slice(0, 8));
        }
      };
      reader.readAsDataURL(file);
    }
  };

  const addImageUrl = () => {
    if (newImageUrl.trim()) {
      setImages((prev) => [...prev, newImageUrl.trim()].slice(0, 8));
      setNewImageUrl("");
      setShowUrlInput(false);
    }
  };

  const removeImage = (index: number) => {
    setImages((prev) => prev.filter((_, i) => i !== index));
  };

  const handleAddVariant = () => {
    if (newVariant.trim()) {
      setVariants((prev) => [...prev, newVariant.trim()]);
      setNewVariant("");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage("");

    if (!name.trim()) {
      setErrorMessage("Vui lòng nhập tên sản phẩm.");
      return;
    }
    if (!price || Number(price) <= 0) {
      setErrorMessage("Vui lòng nhập giá bán hợp lệ (> 0 đồng).");
      return;
    }

    setIsSubmitting(true);

    const productPayload = {
      name: name.trim(),
      price: promoEnabled && Number(promoPrice) > 0 ? Number(promoPrice) : Number(price),
      original_price: Number(originalPrice) || Number(price),
      category0: category0,
      category1: "Sản phẩm mới",
      brand: brand.trim() || "",
      condition: "Mới 100%",
      short_description: shortDesc.trim(),
      description: description.trim() || shortDesc.trim(),
      stock: Number(stock) || 0,
      sku: sku.trim() || `MRC-${Date.now()}`,
      weight: Number(weight) || 0,
      dimensions: `${length || 0}x${width || 0}x${height || 0}`,
      shipper: shipper,
      images: images.length > 0 ? images : ["/placeholder.svg"]
    };

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const res = await fetch(`${apiBase}/seller/products`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(productPayload)
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || "Không thể đăng sản phẩm lên hệ thống.");
      }

      setSuccessToast(true);
      setTimeout(() => {
        router.push("/seller/products");
      }, 1500);
    } catch (err: any) {
      setErrorMessage(err.message || "Lỗi kết nối máy chủ. Vui lòng thử lại.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="seller-add-product-page">
      {/* SUCCESS TOAST */}
      {successToast && (
        <div className="seller-toast">
          <CheckCircle size={20} />
          <span>Đăng bán sản phẩm thành công! Đang chuyển trang...</span>
        </div>
      )}

      {/* BREADCRUMB */}
      <nav className="seller-breadcrumb" aria-label="Đường dẫn">
        <Link href="/seller">Trang chủ</Link>
        <span>›</span>
        <Link href="/seller/products">Sản phẩm</Link>
        <span>›</span>
        <span style={{ color: "#111827", fontWeight: 600 }}>Đăng sản phẩm mới</span>
      </nav>

      {/* PAGE TITLE */}
      <div className="seller-page-title-row">
        <h1>Đăng sản phẩm mới</h1>
        <p>
          Điền đầy đủ thông tin để sản phẩm hiển thị tốt hơn trên MerRec và
          tiếp cận nhiều khách hàng hơn.
        </p>
      </div>

      {errorMessage && (
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "10px",
          padding: "12px 16px",
          background: "#fef2f2",
          border: "1px solid #fecaca",
          borderRadius: "8px",
          color: "#b91c1c",
          marginBottom: "20px",
          fontSize: "14px"
        }}>
          <AlertCircle size={18} />
          <span>{errorMessage}</span>
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="seller-form-layout">
          {/* =========================================
              LEFT COLUMN: HÌNH ẢNH & THÔNG TIN CƠ BẢN
             ========================================= */}
          <div className="seller-form-left-col">
            {/* 1. HÌNH ẢNH SẢN PHẨM */}
            <div className="seller-form-card">
              <div className="seller-form-card-title">
                <div className="seller-form-card-title-left">
                  <ImageIcon size={20} />
                  <span>Hình ảnh sản phẩm</span>
                </div>
                <span className="seller-form-card-hint">
                  Tối đa 8 ảnh. Định dạng JPG, PNG. Kích thước tối đa 5MB/ảnh.
                </span>
              </div>

              {/* DROPZONE */}
              <div
                className="seller-image-dropzone"
                onClick={() => fileInputRef.current?.click()}
              >
                <UploadCloud size={40} className="seller-dropzone-icon" />
                <div className="seller-dropzone-text">
                  Kéo thả hình ảnh vào đây
                </div>
                <div className="seller-dropzone-sub">hoặc</div>
                <button type="button" className="seller-dropzone-choose-btn">
                  <ImageIcon size={16} />
                  <span>Chọn ảnh từ máy tính</span>
                </button>
                <div className="seller-dropzone-sub" style={{ marginTop: "8px" }}>
                  Ảnh nên có nền trắng, rõ nét, kích thước tối thiểu 800x800px
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/png, image/jpeg, image/webp"
                  style={{ display: "none" }}
                  onChange={handleFileChange}
                />
              </div>

              {/* URL INPUT OPTION */}
              <div style={{ marginBottom: "14px" }}>
                {!showUrlInput ? (
                  <button
                    type="button"
                    onClick={() => setShowUrlInput(true)}
                    style={{
                      background: "none",
                      border: "none",
                      color: "#008848",
                      fontSize: "12.5px",
                      fontWeight: 600,
                      cursor: "pointer",
                      padding: 0
                    }}
                  >
                    + Hoặc nhập URL hình ảnh trực tuyến
                  </button>
                ) : (
                  <div style={{ display: "flex", gap: "8px" }}>
                    <input
                      type="url"
                      placeholder="Dán URL hình ảnh https://..."
                      value={newImageUrl}
                      onChange={(e) => setNewImageUrl(e.target.value)}
                      className="seller-input"
                      style={{ fontSize: "12.5px", height: "36px" }}
                    />
                    <button
                      type="button"
                      onClick={addImageUrl}
                      className="seller-btn-primary"
                      style={{ padding: "0 14px", height: "36px", fontSize: "12.5px" }}
                    >
                      Thêm
                    </button>
                  </div>
                )}
              </div>

              {/* SLOTS GRID */}
              <div className="seller-image-slots-grid">
                {images.map((img, idx) => (
                  <div
                    key={idx}
                    className={`seller-image-slot ${idx === 0 ? "is-cover" : ""}`}
                  >
                    <img src={img} alt={`Slot ${idx + 1}`} />
                    {idx === 0 && <span className="seller-cover-badge">Ảnh bìa</span>}
                    <button
                      type="button"
                      className="seller-slot-remove-btn"
                      onClick={() => removeImage(idx)}
                      title="Xóa ảnh"
                    >
                      <X size={12} />
                    </button>
                  </div>
                ))}

                {Array.from({ length: Math.max(0, 8 - images.length) }).slice(0, 4).map((_, i) => (
                  <div
                    key={`empty-${i}`}
                    className="seller-image-slot seller-image-slot-empty"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <Plus size={20} />
                    <span>Thêm ảnh</span>
                  </div>
                ))}
              </div>
            </div>

            {/* 2. THÔNG TIN CƠ BẢN */}
            <div className="seller-form-card">
              <div className="seller-form-card-title">
                <div className="seller-form-card-title-left">
                  <span style={{ fontSize: "18px" }}>📋</span>
                  <span>Thông tin cơ bản</span>
                </div>
              </div>

              {/* TÊN SẢN PHẨM */}
              <div className="seller-field-group">
                <div className="seller-field-label">
                  <label htmlFor="product-name">
                    Tên sản phẩm <span className="req">*</span>
                  </label>
                  <span className="seller-char-counter">{name.length}/120</span>
                </div>
                <input
                  id="product-name"
                  type="text"
                  maxLength={120}
                  placeholder="Nhập tên sản phẩm (tối đa 120 ký tự)"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="seller-input"
                  required
                />
              </div>

              {/* DANH MỤC & THƯƠNG HIỆU */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                <div className="seller-field-group">
                  <div className="seller-field-label">
                    <label htmlFor="product-category">
                      Danh mục <span className="req">*</span>
                    </label>
                  </div>
                  <select
                    id="product-category"
                    value={category0}
                    onChange={(e) => setCategory0(e.target.value)}
                    className="seller-select"
                  >
                    <option value="Thời trang">Thời trang & Phụ kiện</option>
                    <option value="Giày dép">Giày dép</option>
                    <option value="Điện tử">Điện thoại & Phụ kiện công nghệ</option>
                    <option value="Mỹ phẩm">Mỹ phẩm & Chăm sóc sắc đẹp</option>
                    <option value="Đồ gia dụng">Đồ gia dụng & Đời sống</option>
                    <option value="Thể thao">Thể thao & Dã ngoại</option>
                  </select>
                </div>

                <div className="seller-field-group">
                  <div className="seller-field-label">
                    <label htmlFor="product-brand">Thương hiệu</label>
                  </div>
                  <input
                    id="product-brand"
                    type="text"
                    placeholder="Nhập thương hiệu (nếu có)"
                    value={brand}
                    onChange={(e) => setBrand(e.target.value)}
                    className="seller-input"
                  />
                </div>
              </div>

              {/* MÔ TẢ NGẮN */}
              <div className="seller-field-group">
                <div className="seller-field-label">
                  <label htmlFor="product-short-desc">
                    Mô tả ngắn <span className="req">*</span>
                  </label>
                  <span className="seller-char-counter">{shortDesc.length}/200</span>
                </div>
                <textarea
                  id="product-short-desc"
                  maxLength={200}
                  rows={2}
                  placeholder="Nhập mô tả ngắn về sản phẩm (hiển thị trong kết quả tìm kiếm, tối đa 200 ký tự)"
                  value={shortDesc}
                  onChange={(e) => setShortDesc(e.target.value)}
                  className="seller-textarea"
                />
              </div>

              {/* MÔ TẢ CHI TIẾT */}
              <div className="seller-field-group">
                <div className="seller-field-label">
                  <label htmlFor="product-full-desc">
                    Mô tả chi tiết <span className="req">*</span>
                  </label>
                </div>

                {/* TEXT EDITOR TOOLBAR */}
                <div className="seller-editor-toolbar">
                  <select style={{ fontSize: "12px", border: "none", background: "transparent", outline: "none", fontWeight: 600 }}>
                    <option>Đoạn văn</option>
                    <option>Tiêu đề 1</option>
                    <option>Tiêu đề 2</option>
                  </select>
                  <div style={{ width: "1px", height: "16px", background: "#d1d5db", margin: "0 4px" }} />
                  <button type="button" className="seller-editor-btn" title="In đậm"><Bold size={14} /></button>
                  <button type="button" className="seller-editor-btn" title="In nghiêng"><Italic size={14} /></button>
                  <button type="button" className="seller-editor-btn" title="Gạch chân"><Underline size={14} /></button>
                  <button type="button" className="seller-editor-btn" title="Danh sách"><List size={14} /></button>
                  <button type="button" className="seller-editor-btn" title="Danh sách số"><ListOrdered size={14} /></button>
                  <button type="button" className="seller-editor-btn" title="Căn lề"><AlignLeft size={14} /></button>
                  <button type="button" className="seller-editor-btn" title="Chèn liên kết"><LinkIcon size={14} /></button>
                  <button type="button" className="seller-editor-btn" title="Chèn ảnh"><ImageIcon size={14} /></button>
                </div>

                <textarea
                  id="product-full-desc"
                  rows={6}
                  placeholder="Nhận mô tả chi tiết về sản phẩm, bao gồm thông số, công dụng, hướng dẫn sử dụng..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="seller-textarea seller-editor-textarea"
                />
              </div>
            </div>
          </div>

          {/* =========================================
              RIGHT COLUMN: GIÁ BÁN, TỒN KHO, VẬN CHUYỂN
             ========================================= */}
          <div className="seller-form-right-col">
            {/* 1. GIÁ BÁN */}
            <div className="seller-form-card">
              <div className="seller-form-card-title">
                <div className="seller-form-card-title-left">
                  <span style={{ fontSize: "18px" }}>🏷️</span>
                  <span>Giá bán</span>
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "14px" }}>
                <div className="seller-field-group">
                  <div className="seller-field-label">
                    <label htmlFor="original-price">Giá gốc</label>
                  </div>
                  <div className="seller-input-with-suffix">
                    <input
                      id="original-price"
                      type="number"
                      min={0}
                      value={originalPrice}
                      onChange={(e) => setOriginalPrice(e.target.value === "" ? "" : Number(e.target.value))}
                      className="seller-input"
                    />
                    <span className="seller-input-suffix">đồng</span>
                  </div>
                </div>

                <div className="seller-field-group">
                  <div className="seller-field-label">
                    <label htmlFor="selling-price">
                      Giá bán <span className="req">*</span>
                    </label>
                  </div>
                  <div className="seller-input-with-suffix">
                    <input
                      id="selling-price"
                      type="number"
                      min={0}
                      value={price}
                      onChange={(e) => setPrice(e.target.value === "" ? "" : Number(e.target.value))}
                      className="seller-input"
                      required
                    />
                    <span className="seller-input-suffix">đồng</span>
                  </div>
                  <div className="seller-field-hint">Đây là giá hiển thị cho khách hàng</div>
                </div>
              </div>

              {/* BẬT KHUYẾN MÃI SWITCH */}
              <div className="seller-switch-row">
                <span className="seller-switch-label">Bật khuyến mãi</span>
                <label className="seller-switch">
                  <input
                    type="checkbox"
                    checked={promoEnabled}
                    onChange={(e) => setPromoEnabled(e.target.checked)}
                  />
                  <span className="seller-slider"></span>
                </label>
              </div>

              {promoEnabled && (
                <div style={{ background: "#f0fbf5", padding: "14px", borderRadius: "8px", border: "1px solid #bcead1", marginBottom: "12px" }}>
                  <div className="seller-field-group">
                    <div className="seller-field-label">
                      <label htmlFor="promo-price">
                        Giá khuyến mãi <span className="req">*</span>
                      </label>
                    </div>
                    <div className="seller-input-with-suffix">
                      <input
                        id="promo-price"
                        type="number"
                        min={0}
                        value={promoPrice}
                        onChange={(e) => setPromoPrice(e.target.value === "" ? "" : Number(e.target.value))}
                        className="seller-input"
                      />
                      <span className="seller-input-suffix">đồng</span>
                    </div>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                    <div className="seller-field-group">
                      <div className="seller-field-label">
                        <label htmlFor="promo-start">Thời gian bắt đầu</label>
                      </div>
                      <input
                        id="promo-start"
                        type="date"
                        value={startDate}
                        onChange={(e) => setStartDate(e.target.value)}
                        className="seller-input"
                      />
                    </div>
                    <div className="seller-field-group">
                      <div className="seller-field-label">
                        <label htmlFor="promo-end">Thời gian kết thúc</label>
                      </div>
                      <input
                        id="promo-end"
                        type="date"
                        value={endDate}
                        onChange={(e) => setEndDate(e.target.value)}
                        className="seller-input"
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* 2. TỒN KHO & VẬN CHUYỂN */}
            <div className="seller-form-card">
              <div className="seller-form-card-title">
                <div className="seller-form-card-title-left">
                  <span style={{ fontSize: "18px" }}>📦</span>
                  <span>Tồn kho & vận chuyển</span>
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "14px" }}>
                <div className="seller-field-group">
                  <div className="seller-field-label">
                    <label htmlFor="product-stock">
                      Số lượng tồn kho <span className="req">*</span>
                    </label>
                  </div>
                  <div className="seller-input-with-suffix">
                    <input
                      id="product-stock"
                      type="number"
                      min={0}
                      value={stock}
                      onChange={(e) => setStock(e.target.value === "" ? "" : Number(e.target.value))}
                      className="seller-input"
                      required
                    />
                    <span className="seller-input-suffix">Sản phẩm</span>
                  </div>
                </div>

                <div className="seller-field-group">
                  <div className="seller-field-label">
                    <label htmlFor="product-sku">SKU (mã phân loại)</label>
                  </div>
                  <input
                    id="product-sku"
                    type="text"
                    placeholder="VD: KDZ-SP001"
                    value={sku}
                    onChange={(e) => setSku(e.target.value)}
                    className="seller-input"
                  />
                </div>
              </div>

              {/* CÂN NẶNG & KÍCH THƯỚC */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1.3fr", gap: "16px", marginBottom: "14px" }}>
                <div className="seller-field-group">
                  <div className="seller-field-label">
                    <label htmlFor="product-weight">
                      Cân nặng (g) <span className="req">*</span>
                    </label>
                  </div>
                  <div className="seller-input-with-suffix">
                    <input
                      id="product-weight"
                      type="number"
                      min={0}
                      value={weight}
                      onChange={(e) => setWeight(e.target.value === "" ? "" : Number(e.target.value))}
                      className="seller-input"
                    />
                    <span className="seller-input-suffix">gram</span>
                  </div>
                </div>

                <div className="seller-field-group">
                  <div className="seller-field-label">
                    <label>Kích thước (cm)</label>
                  </div>
                  <div style={{ display: "flex", gap: "6px" }}>
                    <input
                      type="number"
                      placeholder="Dài"
                      value={length}
                      onChange={(e) => setLength(e.target.value)}
                      className="seller-input"
                      style={{ padding: "8px 6px", textAlign: "center" }}
                    />
                    <input
                      type="number"
                      placeholder="Rộng"
                      value={width}
                      onChange={(e) => setWidth(e.target.value)}
                      className="seller-input"
                      style={{ padding: "8px 6px", textAlign: "center" }}
                    />
                    <input
                      type="number"
                      placeholder="Cao"
                      value={height}
                      onChange={(e) => setHeight(e.target.value)}
                      className="seller-input"
                      style={{ padding: "8px 6px", textAlign: "center" }}
                    />
                  </div>
                </div>
              </div>

              {/* ĐƠN VỊ VẬN CHUYỂN */}
              <div className="seller-field-group">
                <div className="seller-field-label">
                  <label htmlFor="product-shipper">
                    Đơn vị vận chuyển <span className="req">*</span>
                  </label>
                </div>
                <select
                  id="product-shipper"
                  value={shipper}
                  onChange={(e) => setShipper(e.target.value)}
                  className="seller-select"
                >
                  <option value="MerRec Express">MerRec Express - Giao nhanh tiết kiệm</option>
                  <option value="Giao Hàng Nhanh (GHN)">Giao Hàng Nhanh (GHN)</option>
                  <option value="Viettel Post">Viettel Post</option>
                  <option value="VNPost Tiết Kiệm">VNPost Tiết Kiệm</option>
                </select>
              </div>

              {/* GREEN INFO CALLOUT */}
              <div className="seller-info-callout">
                <Truck size={22} style={{ flexShrink: 0 }} />
                <span>
                  Sản phẩm sẽ được giao hàng thông qua các đối tác vận chuyển
                  của MerRec (Nhanh chóng - An toàn - Tiết kiệm).
                </span>
              </div>
            </div>

            {/* 3. THUỘC TÍNH PHÂN LOẠI */}
            <div className="seller-form-card">
              <div className="seller-form-card-title">
                <div className="seller-form-card-title-left">
                  <span style={{ fontSize: "18px" }}>🎨</span>
                  <span>Thuộc tính phân loại</span>
                </div>
              </div>

              <div style={{ fontSize: "12.5px", color: "#6b7280", marginBottom: "14px" }}>
                Thêm các phân loại như màu sắc, kích thước để khách hàng dễ dàng lựa chọn
              </div>

              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", marginBottom: "14px" }}>
                {variants.map((v, idx) => (
                  <span
                    key={idx}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                      padding: "5px 10px",
                      background: "#f3f4f6",
                      borderRadius: "6px",
                      fontSize: "12.5px",
                      color: "#374151"
                    }}
                  >
                    <span>{v}</span>
                    <button
                      type="button"
                      onClick={() => setVariants(variants.filter((_, i) => i !== idx))}
                      style={{ border: "none", background: "none", cursor: "pointer", padding: 0 }}
                    >
                      <X size={12} color="#9ca3af" />
                    </button>
                  </span>
                ))}
              </div>

              <div style={{ display: "flex", gap: "8px" }}>
                <input
                  type="text"
                  placeholder="VD: Màu sắc (Đỏ, Xanh), Size (L, XL)"
                  value={newVariant}
                  onChange={(e) => setNewVariant(e.target.value)}
                  className="seller-input"
                  style={{ height: "36px", fontSize: "12.5px" }}
                />
                <button
                  type="button"
                  onClick={handleAddVariant}
                  className="seller-btn-secondary"
                  style={{ height: "36px", padding: "0 14px", fontSize: "12.5px" }}
                >
                  Thêm
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* BOTTOM ACTION BAR */}
        <div className="seller-bottom-action-bar">
          <Link href="/seller/products" className="seller-btn-secondary">
            Hủy
          </Link>
          <button
            type="button"
            className="seller-btn-secondary"
            onClick={() => alert("Đã lưu bản nháp thành công!")}
          >
            Lưu bản nháp
          </button>
          <button
            type="submit"
            className="seller-btn-primary"
            disabled={isSubmitting}
          >
            <span>{isSubmitting ? "Đang đăng bán..." : "Đăng bán sản phẩm"}</span>
          </button>
        </div>
      </form>
    </div>
  );
}
