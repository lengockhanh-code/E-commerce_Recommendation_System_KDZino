"use client";

import Link from "next/link";
import "./profile.css";

export default function ProfilePage() {
  return (
    <div className="profile-page-wrapper">
      <div className="container-custom">
        <div className="breadcrumb">
          <Link href="/">Trang chủ</Link> › <span className="current">Tài khoản cá nhân</span>
        </div>

        <div className="profile-layout">
          {/* SIDEBAR */}
          <aside className="profile-sidebar">
            <div className="user-badge-header">
              <div className="avatar-circle">KDZ</div>
              <div>
                <div className="user-name-text">Khách hàng KDZino</div>
                <small style={{ color: "#888" }}>Hội viên Vàng</small>
              </div>
            </div>

            <ul className="profile-menu">
              <li>
                <a href="#" className="menu-item-link active">
                  👤 Thông tin tài khoản
                </a>
              </li>
              <li>
                <a href="#" className="menu-item-link">
                  📦 Đơn hàng của tôi
                </a>
              </li>
              <li>
                <a href="#" className="menu-item-link">
                  ❤️ Sản phẩm yêu thích
                </a>
              </li>
              <li>
                <a href="#" className="menu-item-link">
                  📍 Sổ địa chỉ nhận hàng
                </a>
              </li>
              <li>
                <a href="#" className="menu-item-link">
                  🔔 Thông báo
                </a>
              </li>
            </ul>
          </aside>

          {/* CONTENT */}
          <main className="profile-content-card">
            <h2 className="content-header-title">Hồ sơ cá nhân</h2>

            <form onSubmit={(e) => e.preventDefault()}>
              <div className="form-grid-2">
                <div className="form-group">
                  <label className="form-label">Họ và tên</label>
                  <input type="text" defaultValue="Nguyễn Văn A" className="form-input" />
                </div>

                <div className="form-group">
                  <label className="form-label">Số điện thoại</label>
                  <input type="text" defaultValue="0987654321" className="form-input" />
                </div>

                <div className="form-group">
                  <label className="form-label">Địa chỉ Email</label>
                  <input type="email" defaultValue="khachhang@kdzino.vn" className="form-input" />
                </div>

                <div className="form-group">
                  <label className="form-label">Ngày sinh</label>
                  <input type="date" defaultValue="1998-05-15" className="form-input" />
                </div>
              </div>

              <button type="submit" className="save-btn">
                Lưu thay đổi
              </button>
            </form>
          </main>
        </div>
      </div>
    </div>
  );
}
