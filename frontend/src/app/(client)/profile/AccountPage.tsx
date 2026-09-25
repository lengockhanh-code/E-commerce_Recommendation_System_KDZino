"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import AccountSections from "./AccountSections";
import { accountSections, type AccountSection } from "./account-data";
import { Bell, CalendarDays, ChevronRight, Crown, Gift, Headphones, Heart, Home, Keyboard, LockKeyhole, LogOut, Mail, MapPin, Mouse, Package, Pencil, Percent, Phone, Save, Settings, Truck, UserRound } from "lucide-react";
import "./profile.css";

const menu = [
  { section: "overview", label: "Thông tin tài khoản", icon: UserRound },
  { section: "orders", label: "Đơn hàng của tôi", icon: Package },
  { section: "favorites", label: "Sản phẩm yêu thích", icon: Heart },
  { section: "addresses", label: "Sổ địa chỉ nhận hàng", icon: MapPin },
  { section: "notifications", label: "Thông báo", icon: Bell },
];
const orders = [
  { name: "Tai nghe Bluetooth KDZ", id: "DH001234", status: "Đang giao", tone: "shipping", icon: Headphones },
  { name: "Chuột không dây KDZ", id: "DH001233", status: "Đã giao", tone: "delivered", icon: Mouse },
  { name: "Bàn phím cơ KDZ", id: "DH001232", status: "Đã hủy", tone: "cancelled", icon: Keyboard },
];

export default function AccountPage({ section = "overview", orderId }: { section?: AccountSection; orderId?: string }) {
  const router = useRouter();
  const [profileName, setProfileName] = useState("Nguyễn Văn A");
  const [saved, setSaved] = useState(false);
  const logoutDialog = useRef<HTMLDialogElement>(null);
  const open = (target: string) => {
    if (target === "logout") {
      logoutDialog.current?.showModal();
      return;
    }
    router.push(target === "overview" ? "/profile" : `/profile/${target}`);
  };
  const nameInput = useRef<HTMLInputElement>(null);
  return (
    <div className="account-page">
      <dialog ref={logoutDialog} className="account-logout-dialog" aria-labelledby="logout-title" aria-describedby="logout-description" onClick={(event) => { if (event.target === event.currentTarget) logoutDialog.current?.close(); }}>
        <div className="account-logout-content">
          <span className="account-logout-icon"><LogOut size={27} /></span>
          <h2 id="logout-title">Đăng xuất tài khoản?</h2>
          <p id="logout-description">Bạn có chắc muốn đăng xuất? Bạn có thể đăng nhập lại bất cứ lúc nào.</p>
          <div className="account-logout-actions">
            <button type="button" className="account-action secondary" autoFocus onClick={() => logoutDialog.current?.close()}>Hủy</button>
            <button type="button" className="account-action" onClick={() => { logoutDialog.current?.close(); router.push("/login"); }}>Đăng xuất</button>
          </div>
        </div>
      </dialog>
      <div className="account-container">
        <nav className="account-breadcrumb" aria-label="Đường dẫn">
          <Link href="/"><Home size={16} /><span>Trang chủ</span></Link>
          <ChevronRight size={13} /><Link href="/profile">Tài khoản cá nhân</Link>
          <ChevronRight size={13} /><span aria-current="page">{orderId ? "Chi tiết đơn hàng" : accountSections[section]}</span>
        </nav>
        <div className="account-layout">
          <aside className="account-sidebar account-card">
            <h2>Tài khoản của tôi</h2>
            <nav className="account-menu" aria-label="Tài khoản của tôi">
              {menu.map(({ label, icon: Icon, section: target }) => (
                <button type="button" key={label} onClick={() => open(target)} className={section === target ? "is-active" : ""} aria-current={section === target ? "page" : undefined}>
                  <Icon size={20} /><span>{label}</span>
                </button>
              ))}
              <div className="account-menu-divider" />
              <button type="button" onClick={() => open("password")} className={section === "password" ? "is-active" : ""} aria-current={section === "password" ? "page" : undefined}><LockKeyhole size={20} /><span>Đổi mật khẩu</span></button>
              <button type="button" onClick={() => open("settings")} className={section === "settings" ? "is-active" : ""} aria-current={section === "settings" ? "page" : undefined}><Settings size={20} /><span>Cài đặt</span></button>
              <button type="button" onClick={() => open("logout")} className={section === "logout" ? "is-active" : ""} aria-current={section === "logout" ? "page" : undefined}><LogOut size={20} /><span>Đăng xuất</span></button>
            </nav>
            <div className="account-support">
              <div className="account-support-heading"><span className="account-support-icon"><Headphones size={27} /></span><div><strong>Cần hỗ trợ?</strong><p>Liên hệ với chúng tôi</p></div></div>
              <button type="button" onClick={() => open("support")}>Liên hệ ngay</button>
            </div>
          </aside>

          {section === "overview" ? <section className="account-details account-card" aria-labelledby="account-title">
            <h1 id="account-title">Thông tin tài khoản</h1>
            <p className="account-subtitle">Cập nhật thông tin cá nhân để trải nghiệm dịch vụ tốt hơn</p>
            <div className="account-identity">
              <div className="account-identity-text">
                <div className="account-name"><h2>{profileName}</h2><button type="button" aria-label="Chỉnh sửa họ tên" onClick={() => nameInput.current?.focus()}><Pencil size={15} /></button></div>
                <div className="account-member"><Crown size={23} fill="currentColor" strokeWidth={1} />Hội viên Vàng</div>
                <p>Thành viên từ 15/06/2023</p>
              </div>
              <Crown className="account-identity-crown" size={100} strokeWidth={1} fill="currentColor" aria-hidden="true" />
            </div>
            <form onSubmit={(event) => { event.preventDefault(); setProfileName(String(new FormData(event.currentTarget).get("name"))); setSaved(true); }}>
              <h2 className="account-section-title"><UserRound size={20} fill="currentColor" />Thông tin cá nhân</h2>
              <div className="account-form-grid">
                <div className="account-field"><label htmlFor="account-name">Họ và tên <span>*</span></label><div className="account-input"><UserRound size={19} /><input ref={nameInput} id="account-name" name="name" autoComplete="name" defaultValue="Nguyễn Văn A" required /></div></div>
                <div className="account-field"><label htmlFor="account-phone">Số điện thoại <span>*</span></label><div className="account-input"><Phone size={18} /><input id="account-phone" name="phone" type="tel" autoComplete="tel" defaultValue="0987654321" required /></div></div>
                <div className="account-field"><label htmlFor="account-email">Địa chỉ Email <span>*</span></label><div className="account-input"><Mail size={19} /><input id="account-email" name="email" type="email" autoComplete="email" defaultValue="khachhang@kdzino.vn" required /></div></div>
                <div className="account-field"><label htmlFor="account-birthday">Ngày sinh</label><div className="account-input"><CalendarDays size={19} /><input id="account-birthday" name="birthday" type="date" autoComplete="bday" defaultValue="1998-05-15" /></div></div>
              </div>
              {saved && <p className="account-feedback" role="status">Đã cập nhật bản xem trước. Thông tin chưa được lưu vào tài khoản.</p>}
              <button type="submit" className="account-save account-save-compact"><Save size={18} />Lưu thay đổi</button>
            </form>
          </section> : <AccountSections key={`${section}-${orderId ?? ""}`} section={section} orderId={orderId} />}

          <aside className="account-widgets" aria-label="Tiện ích tài khoản">
            <section className="account-gold">
              <Crown className="account-gold-watermark" size={114} fill="currentColor" strokeWidth={1} aria-hidden="true" />
              <div className="account-gold-title"><Crown size={40} fill="currentColor" strokeWidth={1} /><div><h2>Hội viên Vàng</h2><p>Tận hưởng nhiều ưu đãi đặc biệt</p></div></div>
              <div className="account-perks">
                <div><span><Truck size={22} /></span><p>Miễn phí<br />vận chuyển</p></div>
                <div><span><Percent size={23} /></span><p>Ưu đãi<br />độc quyền</p></div>
                <div><span><Gift size={23} /></span><p>Tích điểm<br />đổi quà</p></div>
              </div>
              <button type="button" className="account-perks-button" onClick={() => open("membership")}>Xem đặc quyền<ChevronRight size={16} /></button>
            </section>
            <section className="account-orders account-card">
              <div className="account-widget-heading"><h2><Package size={18} />Đơn hàng gần đây</h2><button type="button" onClick={() => open("orders")}>Xem tất cả<ChevronRight size={14} /></button></div>
              <div>{orders.map(({ name, id, status, tone, icon: Icon }) => <button type="button" className="account-order" key={id} onClick={() => open(`orders/${id}`)}>
                <span className="account-order-image"><Icon size={31} strokeWidth={1.6} /></span><span className="account-order-info"><strong>{name}</strong><small>#{id}</small></span><span className={`account-order-status ${tone}`}>{status}</span><ChevronRight size={17} className="account-order-arrow" />
              </button>)}</div>
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
}
