"use client";

import { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import "./login.css";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedTarget = searchParams.get("redirect") || searchParams.get("next") || "/";
  const redirectTarget = requestedTarget.startsWith("/") && !requestedTarget.startsWith("//") && !requestedTarget.includes("\\") ? requestedTarget : "/";

  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    const fragment = new URLSearchParams(window.location.hash.slice(1));
    const token = fragment.get("token");
    if (token) {
      window.history.replaceState({}, "", "/login");
      localStorage.setItem("merrec_token", token);
      localStorage.removeItem("merrec_user");
      window.location.replace("/");
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");
    setIsLoading(true);
    try {
      await login(email, password);
      router.push(redirectTarget);
    } catch (err: any) {
      setErrorMsg(err.message || "Đăng nhập thất bại. Vui lòng kiểm tra lại thông tin.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    setErrorMsg("");
    try {
      // Redirect to FastAPI Google Login URL or handle SDK
      window.location.href = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"}/auth/google/login`;
    } catch (err: any) {
      setErrorMsg(err.message || "Không thể kết nối dịch vụ Google OAuth.");
    }
  };

  const handleFacebookLogin = () => {
    setErrorMsg("Chức năng Đăng nhập với Facebook đang được kết nối với Facebook App ID.");
  };

  return (
    <div className="moho-auth-page">
      <div className="moho-auth-container">
        {/* LEFT COLUMN */}
        <div className="moho-auth-left">
          <h1 className="moho-title">Đăng nhập</h1>
          <p className="moho-subtitle">
            Đăng nhập để tích lũy điểm và nhận ưu đãi từ KDZino.
          </p>
          <div className="moho-title-line" />

          {/* SOCIAL BUTTONS ON LEFT COLUMN */}
          <div className="moho-social-btns">
            <button
              type="button"
              className="moho-social-btn google"
              onClick={handleGoogleLogin}
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
              onClick={handleFacebookLogin}
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
            <div className="moho-input-field">
              <input
                type="email"
                placeholder="Nhập email của bạn"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="username"
              />
            </div>

            <div className="moho-input-field">
              <input
                type="password"
                placeholder="Mật khẩu"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>

            <p className="moho-disclaimer">
              Website được bảo vệ bởi reCAPTCHA và{" "}
              <Link href="#">Chính sách bảo mật</Link> và{" "}
              <Link href="#">Điều khoản dịch vụ</Link> của Google.
            </p>

            {/* SUBMIT ROW WITH FORGOT & REGISTER LINKS */}
            <div className="moho-submit-row">
              <button type="submit" className="moho-submit-btn" disabled={isLoading}>
                {isLoading ? "ĐANG XỬ LÝ..." : "ĐĂNG NHẬP"}
              </button>

              <div className="moho-submit-links">
                <Link href="#" className="moho-link-forgot">
                  Quên mật khẩu?
                </Link>
                <div className="moho-link-register">
                  hoặc <Link href={`/register${redirectTarget !== "/" ? `?redirect=${encodeURIComponent(redirectTarget)}` : ""}`}>Đăng ký</Link>
                </div>
              </div>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div style={{ padding: "40px", textAlign: "center" }}>Đang tải...</div>}>
      <LoginForm />
    </Suspense>
  );
}