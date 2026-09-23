"use client";

import Image from "next/image";
import Link from "next/link";
import { FaFacebookF, FaYoutube, FaTiktok, FaInstagram } from "react-icons/fa";
import "./Footer.css";

export default function Footer() {
  return (
    <footer className="footer">
      <div className="footer-inner">
        {/* CỘT 1: LOGO PHÓNG TO VÀ CÁC ICON NẰM GIỮA */}
        <div className="footer-brand">
          <Link href="/" className="footer-logo-link">
            <Image
              src="/kdz_logo.png"
              alt="KDZino"
              width={220}
              height={75}
              priority
              className="footer-logo"
            />
          </Link>

          <div className="footer-socials">
            <a href="#" className="social-btn-circle" title="Facebook">
              <FaFacebookF size={16} />
            </a>
            <a href="#" className="social-btn-circle" title="YouTube">
              <FaYoutube size={17} />
            </a>
            <a href="#" className="social-btn-circle" title="TikTok">
              <FaTiktok size={15} />
            </a>
            <a href="#" className="social-btn-circle" title="Instagram">
              <FaInstagram size={17} />
            </a>
            <a href="#" className="social-btn-circle" title="Zalo">
              <span style={{ fontSize: "11px", fontWeight: "900", letterSpacing: "-0.5px" }}>Zalo</span>
            </a>
          </div>
        </div>

        {/* CỘT 2: VỀ KDZ */}
        <div className="footer-col">
          <h4 className="footer-col-title">Về KDZ</h4>
          <div className="footer-links-list">
            <Link href="#">Giới thiệu</Link>
            <Link href="#">Tin tức</Link>
            <Link href="#">Tuyển dụng</Link>
            <Link href="#">Liên hệ</Link>
          </div>
        </div>

        {/* CỘT 3: HỖ TRỢ KHÁCH HÀNG */}
        <div className="footer-col">
          <h4 className="footer-col-title">Hỗ trợ khách hàng</h4>
          <div className="footer-links-list">
            <Link href="#">Trung tâm trợ giúp</Link>
            <Link href="#">Hướng dẫn mua hàng</Link>
            <Link href="#">Chính sách đổi trả</Link>
            <Link href="#">Chính sách bảo mật</Link>
            <Link href="#">Điều khoản sử dụng</Link>
          </div>
        </div>

        {/* CỘT 4: PHƯƠNG THỨC THANH TOÁN - GỌN GÀNG 2 HÀNG THẲNG */}
        <div className="footer-col">
          <h4 className="footer-col-title">Phương thức thanh toán</h4>
          <div className="payment-grid">
            <div className="pay-row">
              <span className="pay-logo-badge" style={{ color: "#1a1f71", fontWeight: "900" }}>VISA</span>
              <span className="pay-logo-badge" style={{ color: "#eb001b", fontWeight: "800" }}>Mastercard</span>
              <span className="pay-logo-badge" style={{ background: "#a50064", color: "#fff", border: "none" }}>MoMo</span>
              <span className="pay-logo-badge" style={{ color: "#0088ff", fontWeight: "800" }}>ZaloPay</span>
            </div>

            <div className="pay-row">
              <span className="pay-logo-badge" style={{ background: "#ee4d2d", color: "#fff", border: "none" }}>ShopeePay</span>
              <span className="pay-logo-badge" style={{ color: "#005baa", fontWeight: "900" }}>VNPAY</span>
              <span className="pay-logo-badge" style={{ background: "#000", color: "#fff", border: "none" }}>Apple Pay</span>
            </div>
          </div>
        </div>

        {/* CỘT 5: TẢI ỨNG DỤNG KDZ & QR CODE */}
        <div className="footer-col">
          <h4 className="footer-col-title">Tải ứng dụng KDZ</h4>

          <div className="app-download-container">
            <div className="app-store-btns">
              <a href="#" className="download-badge-btn">
                <span>🍎</span> App Store
              </a>
              <a href="#" className="download-badge-btn">
                <span>🤖</span> Google Play
              </a>
            </div>

            <div className="qr-code-box">
              <img
                src="https://api.qrserver.com/v1/create-qr-code/?size=100x100&data=https://kdz.vn"
                alt="QR Code"
              />
            </div>
          </div>

          <div className="qr-note-sub">Quét mã để tải ứng dụng</div>
        </div>
      </div>

      {/* BANNER BẢO LƯU BẢN QUYỀN CHÂN TRANG */}
      <div className="footer-bottom-bar">
        <div className="footer-bottom-content">
          <div>© 2024 KDZ. Tất cả các quyền được bảo lưu.</div>

          <div className="legal-links">
            <a href="#">Điều khoản sử dụng</a>
            <span>|</span>
            <a href="#">Chính sách bảo mật</a>
            <span>|</span>
            <a href="#">Chính sách cookie</a>
          </div>
        </div>
      </div>
    </footer>
  );
}