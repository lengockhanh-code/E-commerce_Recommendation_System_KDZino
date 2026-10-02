"use client";

import { useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import "./register.css";

function RegisterForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTarget = searchParams.get("redirect") || searchParams.get("next") || "/";

  const { register } = useAuth();
  const [regMethod, setRegMethod] = useState<"email" | "phone">("email");
  const [lastName, setLastName] = useState("");
  const [firstName, setFirstName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");
    setIsLoading(true);

    const fullName = `${lastName} ${firstName}`.trim() || "Khách hàng KDZino";
    const userEmail = regMethod === "email" ? email : `${phone}@kdzino.vn`;

    try {
      await register(fullName, userEmail, password);
      router.push("/onboarding");
    } catch (err: any) {
      setErrorMsg(err.message || "Đăng ký không thành công.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="moho-auth-page">
      <div className="moho-auth-container">
        {/* LEFT COLUMN */}
        <div className="moho-auth-left">
          <h1 className="moho-title">Tạo tài khoản</h1>
          <p className="moho-subtitle">
            Đăng ký tài khoản chỉ trong 1 phút để tích lũy điểm và nhận ưu đãi từ KDZino.
          </p>
          <div className="moho-title-line" />

          {/* SOCIAL BUTTONS ON LEFT COLUMN */}
          <div className="moho-social-btns">
            <button
              type="button"
              className="moho-social-btn google"
              onClick={() => { window.location.href = "http://localhost:8000/api/v1/auth/google/login"; }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" style={{ flexShrink: 0 }}>
                <path fill="#4285F4" d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17z"/>
                <path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.26v3.15C3.25 21.3 7.31 24 12 24z"/>
                <path fill="#FBBC05" d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.26C.46 8.17 0 9.97 0 12s.46 3.83 1.26 5.42l4.02-3.15z"/>
                <path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.31 0 3.25 2.7 1.26 6.58l4.02 3.15c.95-2.83 3.6-4.98 6.72-4.98z"/>
              </svg>
              <span>Đăng nhập bằng Google</span>
            </button>

            <button
              type="button"
              className="moho-social-btn facebook"
              onClick={() => { setErrorMsg("Chức năng Đăng nhập với Facebook đang được kết nối với Facebook App ID."); }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="#ffffff" style={{ flexShrink: 0 }}>
                <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
              </svg>
              <span>Tiếp tục với Facebook</span>
            </button>
          </div>
        </div>

        {/* RIGHT COLUMN */}
        <div className="moho-auth-right">
          {errorMsg && (
            <div style={{ color: "#dc2626", background: "#fef2f2", border: "1px solid #fecaca", padding: "10px 14px", borderRadius: "6px", fontSize: "13px", marginBottom: "16px" }}>
              {errorMsg}
            </div>
          )}

          <form className="moho-form" onSubmit={handleSubmit}>
            {/* METHOD SELECTOR */}
            <div className="moho-method-group">
              <label className="moho-radio-label">
                <input
                  type="radio"
                  name="regMethod"
                  checked={regMethod === "email"}
                  onChange={() => setRegMethod("email")}
                />
                <span>Đăng ký bằng email</span>
              </label>

              <label className="moho-radio-label">
                <input
                  type="radio"
                  name="regMethod"
                  checked={regMethod === "phone"}
                  onChange={() => setRegMethod("phone")}
                />
                <span>Đăng ký bằng số điện thoại</span>
              </label>
            </div>

            {/* HO INPUT */}
            <div className="moho-input-field">
              <input
                type="text"
                placeholder="Họ"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                required
              />
            </div>

            {/* TEN INPUT */}
            <div className="moho-input-field">
              <input
                type="text"
                placeholder="Tên"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                required
              />
            </div>

            {/* DYNAMIC EMAIL OR PHONE INPUT */}
            {regMethod === "email" ? (
              <div className="moho-input-field">
                <input
                  type="email"
                  placeholder="Email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
            ) : (
              <div className="moho-input-field">
                <input
                  type="tel"
                  placeholder="Số điện thoại"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  required
                />
              </div>
            )}

            {/* PASSWORD INPUT */}
            <div className="moho-input-field">
              <input
                type="password"
                placeholder="Mật khẩu (ít nhất 6 ký tự)"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={6}
                required
              />
            </div>

            {/* RECAPTCHA DISCLAIMER */}
            <p className="moho-disclaimer">
              Website được bảo vệ bởi reCAPTCHA và{" "}
              <Link href="#">Chính sách bảo mật</Link> và{" "}
              <Link href="#">Điều khoản dịch vụ</Link> của Google.
            </p>

            {/* SUBMIT BUTTON */}
            <button type="submit" className="moho-submit-btn" disabled={isLoading}>
              {isLoading ? "ĐANG XỬ LÝ..." : "ĐĂNG KÝ"}
            </button>
          </form>

          {/* FOOTER ACTIONS */}
          <div className="moho-footer-actions">
            <Link href="/" className="moho-back-home">
              ← Quay lại trang chủ
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={<div style={{ padding: "40px", textAlign: "center" }}>Đang tải...</div>}>
      <RegisterForm />
    </Suspense>
  );
}