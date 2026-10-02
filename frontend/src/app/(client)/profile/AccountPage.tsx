"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import AccountSections from "./AccountSections";
import { accountSections, type AccountSection } from "./account-data";
import { Bell, CalendarDays, Check, ChevronRight, Crown, Filter, Gift, Headphones, Heart, History, Home, Keyboard, LockKeyhole, LogOut, Mail, MapPin, Mouse, Package, Pencil, Percent, Phone, Save, Settings, Truck, UserRound } from "lucide-react";
import "./profile.css";

const menu = [
  { section: "overview", label: "Thông tin tài khoản", icon: UserRound },
  { section: "orders", label: "Đơn hàng của tôi", icon: Package },
  { section: "favorites", label: "Sản phẩm yêu thích", icon: Heart },
  { section: "history", label: "Lịch sử hoạt động", icon: History },
  { section: "addresses", label: "Sổ địa chỉ nhận hàng", icon: MapPin },
  { section: "notifications", label: "Thông báo", icon: Bell },
];
const orders = [
  { name: "Tai nghe Bluetooth KDZ", id: "DH001234", status: "Đang giao", tone: "shipping", icon: Headphones },
  { name: "Chuột không dây KDZ", id: "DH001233", status: "Đã giao", tone: "delivered", icon: Mouse },
  { name: "Bàn phím cơ KDZ", id: "DH001232", status: "Đã hủy", tone: "cancelled", icon: Keyboard },
];

interface HistoryFilterWidgetProps {
  selectedTypes: string[];
  setSelectedTypes: React.Dispatch<React.SetStateAction<string[]>>;
  onApply: () => void;
}

function HistoryFilterWidget({ selectedTypes, setSelectedTypes, onApply }: HistoryFilterWidgetProps) {
  const [dateRange, setDateRange] = useState("01/09/2026 - 25/09/2026");

  const toggleType = (type: string) => {
    if (type === "all") {
      setSelectedTypes(["all"]);
      return;
    }
    let next = selectedTypes.filter((t) => t !== "all");
    if (next.includes(type)) {
      next = next.filter((t) => t !== type);
    } else {
      next.push(type);
    }
    if (next.length === 0) next = ["all"];
    setSelectedTypes(next);
  };

  return (
    <aside className="account-widgets history-filter-widget" aria-label="Lọc hoạt động">
      <div className="history-filter-card account-card">
        <div className="filter-widget-header">
          <Filter size={18} className="filter-icon" />
          <h2>Lọc hoạt động</h2>
        </div>

        <div className="filter-group">
          <label className="filter-label">Khoảng thời gian</label>
          <div className="filter-date-input">
            <CalendarDays size={16} />
            <select value={dateRange} onChange={(e) => setDateRange(e.target.value)}>
              <option value="01/09/2026 - 25/09/2026">01/09/2026 - 25/09/2026</option>
              <option value="01/08/2026 - 31/08/2026">01/08/2026 - 31/08/2026</option>
              <option value="01/07/2026 - 31/07/2026">01/07/2026 - 31/07/2026</option>
            </select>
          </div>
        </div>

        <div className="filter-group">
          <label className="filter-label">Loại hoạt động</label>
          <div className="filter-checkbox-list">
            {[
              { id: "all", label: "Tất cả" },
              { id: "view", label: "Xem sản phẩm" },
              { id: "favorite", label: "Yêu thích" },
              { id: "cart", label: "Thêm giỏ hàng" },
              { id: "order", label: "Đặt hàng" },
              { id: "rating", label: "Đánh giá" },
            ].map((item) => (
              <label className="filter-checkbox-row" key={item.id}>
                <input
                  type="checkbox"
                  checked={selectedTypes.includes(item.id)}
                  onChange={() => toggleType(item.id)}
                />
                <span className="checkbox-custom">
                  {selectedTypes.includes(item.id) && <Check size={12} strokeWidth={3} />}
                </span>
                <span className="checkbox-label">{item.label}</span>
              </label>
            ))}
          </div>
        </div>

        <button type="button" className="filter-apply-btn" onClick={onApply}>
          Áp dụng
        </button>
      </div>
    </aside>
  );
}

import { useAuth } from "@/lib/auth-context";

export default function AccountPage({ section = "overview", orderId }: { section?: AccountSection; orderId?: string }) {
  const router = useRouter();
  const { user, token, logout, isLoading, updateUser } = useAuth();
  const [profileName, setProfileName] = useState(user?.full_name || user?.email || "Khách hàng MerRec");
  const [savedMessage, setSavedMessage] = useState("");
  const [filterTypes, setFilterTypes] = useState<string[]>(["all"]);
  const [appliedFilterTypes, setAppliedFilterTypes] = useState<string[]>(["all"]);
  const logoutDialog = useRef<HTMLDialogElement>(null);
  const nameInput = useRef<HTMLInputElement>(null);

  const isGoogleUser = user?.provider === "google";

  useEffect(() => {
    if (isGoogleUser && section === "password") {
      router.replace("/profile");
    }
  }, [isGoogleUser, section, router]);

  useEffect(() => {
    if (user?.full_name) {
      setProfileName(user.full_name);
    }
  }, [user]);

  if (!isLoading && !user) {
    const target = section !== "overview" ? `/profile/${section}` : "/profile";
    return (
      <div className="account-page" style={{ padding: "80px 20px" }}>
        <div
          className="account-container"
          style={{
            maxWidth: "540px",
            margin: "0 auto",
            textAlign: "center",
            background: "#ffffff",
            padding: "40px 30px",
            borderRadius: "12px",
            boxShadow: "0 6px 24px rgba(0,0,0,0.08)",
            border: "1px solid #ebf0ec",
          }}
        >
          <div
            style={{
              width: "64px",
              height: "64px",
              background: "#eaf6f0",
              color: "#088751",
              borderRadius: "50%",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 20px auto",
            }}
          >
            <UserRound size={32} />
          </div>
          <h2 style={{ fontSize: "22px", fontWeight: 700, color: "#111111", marginBottom: "12px" }}>
            Yêu cầu đăng nhập
          </h2>
          <p style={{ fontSize: "14px", color: "#555555", lineHeight: 1.6, marginBottom: "28px" }}>
            Bạn cần đăng nhập tài khoản KDZino để xem và sử dụng tính năng{" "}
            <strong>{accountSections[section] || "Tài khoản cá nhân"}</strong>.
          </p>
          <div style={{ display: "flex", gap: "12px", justifyContent: "center", flexWrap: "wrap" }}>
            <Link href="/" className="shopee-btn-secondary" style={{ textDecoration: "none", height: "44px", borderRadius: "6px", padding: "0 24px" }}>
              Trở về trang chủ
            </Link>
            <Link
              href={`/login?redirect=${encodeURIComponent(target)}`}
              className="shopee-btn-primary"
              style={{ textDecoration: "none", height: "44px", borderRadius: "6px", padding: "0 28px" }}
            >
              Đăng nhập ngay
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const open = (target: string) => {
    if (target === "logout") {
      logoutDialog.current?.showModal();
      return;
    }
    router.push(target === "overview" ? "/profile" : `/profile/${target}`);
  };

  const hasWidgets = section === "overview" || section === "history";

  const handleProfileSave = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const newName = String(formData.get("name") || "").trim();

    if (!newName) return;

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const res = await fetch(`${apiBase}/profile`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ full_name: newName })
      });

      if (!res.ok) throw new Error("Không thể cập nhật thông tin.");

      const updatedData = await res.json();
      updateUser({ full_name: updatedData.full_name || newName });
      setProfileName(updatedData.full_name || newName);
      setSavedMessage("Cập nhật thông tin thành công!");
    } catch {
      updateUser({ full_name: newName });
      setProfileName(newName);
      setSavedMessage("Đã lưu thông tin tài khoản!");
    }
  };

  return (
    <div className="account-page">
      <dialog ref={logoutDialog} className="account-logout-dialog" aria-labelledby="logout-title" aria-describedby="logout-description" onClick={(event) => { if (event.target === event.currentTarget) logoutDialog.current?.close(); }}>
        <div className="account-logout-content">
          <span className="account-logout-icon"><LogOut size={27} /></span>
          <h2 id="logout-title">Đăng xuất tài khoản?</h2>
          <p id="logout-description">Bạn có chắc muốn đăng xuất? Bạn có thể đăng nhập lại bất cứ lúc nào.</p>
          <div className="account-logout-actions">
            <button type="button" className="account-action secondary" autoFocus onClick={() => logoutDialog.current?.close()}>Hủy</button>
            <button type="button" className="account-action" onClick={() => { logoutDialog.current?.close(); logout(); router.push("/"); }}>Đăng xuất</button>
          </div>
        </div>
      </dialog>
      <div className="account-container">
        <nav className="account-breadcrumb" aria-label="Đường dẫn">
          <Link href="/"><Home size={16} /><span>Trang chủ</span></Link>
          <ChevronRight size={13} /><Link href="/profile">Tài khoản cá nhân</Link>
          <ChevronRight size={13} /><span aria-current="page">{orderId ? "Chi tiết đơn hàng" : accountSections[section]}</span>
        </nav>
        <div className={`account-layout ${hasWidgets ? "has-widgets" : "full-width-section"}`}>
          <aside className="account-sidebar account-card">
            <h2>Tài khoản của tôi</h2>
            <nav className="account-menu" aria-label="Tài khoản của tôi">
              {menu.map(({ label, icon: Icon, section: target }) => (
                <button type="button" key={label} onClick={() => open(target)} className={section === target ? "is-active" : ""} aria-current={section === target ? "page" : undefined}>
                  <Icon size={20} /><span>{label}</span>
                </button>
              ))}
              <div className="account-menu-divider" />
              {!isGoogleUser && (
                <button type="button" onClick={() => open("password")} className={section === "password" ? "is-active" : ""} aria-current={section === "password" ? "page" : undefined}>
                  <LockKeyhole size={20} /><span>Đổi mật khẩu</span>
                </button>
              )}
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
            <form onSubmit={handleProfileSave}>
              <h2 className="account-section-title"><UserRound size={20} fill="currentColor" />Thông tin cá nhân</h2>
              <div className="account-form-grid">
                <div className="account-field"><label htmlFor="account-name">Họ và tên <span>*</span></label><div className="account-input"><UserRound size={19} /><input ref={nameInput} id="account-name" name="name" autoComplete="name" defaultValue={user?.full_name || ""} required /></div></div>
                <div className="account-field"><label htmlFor="account-phone">Số điện thoại</label><div className="account-input"><Phone size={18} /><input id="account-phone" name="phone" type="tel" autoComplete="tel" placeholder="Chưa cập nhật" /></div></div>
                <div className="account-field"><label htmlFor="account-email">Địa chỉ Email <span>*</span></label><div className="account-input"><Mail size={19} /><input id="account-email" name="email" type="email" autoComplete="email" value={user?.email || ""} readOnly disabled /></div></div>
                <div className="account-field"><label htmlFor="account-birthday">Ngày sinh</label><div className="account-input"><CalendarDays size={19} /><input id="account-birthday" name="birthday" type="date" autoComplete="bday" /></div></div>
              </div>
              {savedMessage && <p className="account-feedback" role="status">{savedMessage}</p>}
              <button type="submit" className="account-save account-save-compact"><Save size={18} />Lưu thay đổi</button>
            </form>
          </section> : <AccountSections key={`${section}-${orderId ?? ""}`} section={section} orderId={orderId} filterTypes={appliedFilterTypes} />}

          {section === "overview" && (
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
          )}

          {section === "history" && (
            <HistoryFilterWidget
              selectedTypes={filterTypes}
              setSelectedTypes={setFilterTypes}
              onApply={() => setAppliedFilterTypes([...filterTypes])}
            />
          )}
        </div>
      </div>
    </div>
  );
}
