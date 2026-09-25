"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { Bell, Check, CheckCheck, ChevronLeft, ChevronRight, Crown, Eye, EyeOff, Gift, Headphones, Heart, Keyboard, LockKeyhole, MapPin, MessageCircle, Mouse, Package, Pencil, Plus, Search, Settings, ShieldCheck, Trash2, Truck } from "lucide-react";
import { accountSections, demoOrders, displayMoney, type AccountSection } from "./account-data";

const demoNotice = "Bản xem trước: thay đổi chỉ áp dụng trên giao diện, chưa lưu vào tài khoản.";
function ProductIcon({ kind, size = 40 }: { kind: string; size?: number }) {
  const Icon = kind === "headphones" ? Headphones : kind === "mouse" ? Mouse : Keyboard;
  return <Icon size={size} strokeWidth={1.4} />;
}
function Empty({ text }: { text: string }) {
  return <div className="account-empty"><Package size={42} /><h2>{text}</h2><p>Hãy khám phá thêm những sản phẩm dành cho bạn.</p><Link className="account-action" href="/products">Khám phá sản phẩm</Link></div>;
}
function Orders({ orderId }: { orderId?: string }) {
  const [tab, setTab] = useState("Tất cả");
  const [search, setSearch] = useState("");
  const order = demoOrders.find((item) => item.id === orderId);
  if (order) return <div className="account-order-detail">
    <Link className="account-back" href="/profile/orders"><ChevronLeft size={16} />Tất cả đơn hàng</Link>
    <div className="account-panel-head"><div><h2>Đơn hàng #{order.id}</h2><p>Đặt ngày {order.date}</p></div><span className={`account-order-status ${order.tone}`}>{order.status}</span></div>
    {order.status === "Đã hủy" ? <div className="account-info-note">Đơn hàng đã được hủy. Không có khoản thanh toán cần thực hiện.</div> : <ol className="account-timeline">{["Đã đặt hàng", "Đã xác nhận", "Đang giao", "Đã nhận hàng"].map((step, index) => <li className={index < (order.status === "Đã giao" ? 4 : 3) ? "done" : ""} key={step}><span><Check size={15} /></span>{step}</li>)}</ol>}
    <div className="account-inset"><h3><MapPin size={18} />Địa chỉ nhận hàng</h3><strong>Nguyễn Văn A · 0987654321</strong><p>123 Nguyễn Văn Linh, Phường Tân Phong, TP. Hồ Chí Minh</p></div>
    <div className="account-line-product"><span className="account-product-art"><ProductIcon kind={order.kind} /></span><div><strong>{order.name}</strong><p>Số lượng: 1 · Phân loại: Đen</p></div><strong>{displayMoney(order.price)}</strong></div>
    <dl className="account-totals"><div><dt>Tạm tính</dt><dd>{displayMoney(order.price)}</dd></div><div><dt>Phí vận chuyển</dt><dd>Miễn phí</dd></div><div><dt>Phương thức thanh toán</dt><dd>Thanh toán khi nhận hàng</dd></div><div><dt>Tổng cộng</dt><dd>{displayMoney(order.price)}</dd></div></dl>
    <div className="account-actions"><Link className="account-action secondary" href="/profile/support">Liên hệ hỗ trợ</Link><Link className="account-action" href="/products">Tiếp tục mua sắm</Link></div>
  </div>;
  const filtered = demoOrders.filter((item) => (tab === "Tất cả" || item.status === tab) && (item.name + item.id).toLowerCase().includes(search.toLowerCase()));
  return <><div className="account-tabs" aria-label="Lọc trạng thái đơn hàng">{["Tất cả", "Chờ xác nhận", "Đang giao", "Đã giao", "Đã hủy"].map((label) => <button type="button" aria-pressed={tab === label} className={tab === label ? "selected" : ""} key={label} onClick={() => setTab(label)}>{label}</button>)}</div>
    <label className="account-search"><Search size={19} /><input aria-label="Tìm đơn hàng" placeholder="Tìm theo mã đơn hoặc tên sản phẩm" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
    {filtered.length ? filtered.map((item) => <article className="account-order-card" key={item.id}><div className="account-panel-head"><strong>#{item.id}<small>{item.date}</small></strong><span className={`account-order-status ${item.tone}`}>{item.status}</span></div><div className="account-line-product"><span className="account-product-art"><ProductIcon kind={item.kind} /></span><div><strong>{item.name}</strong><p>Phân loại: Đen · Số lượng: 1</p></div></div><div className="account-panel-head"><span>Thành tiền: <strong>{displayMoney(item.price)}</strong></span><Link className="account-action secondary" href={`/profile/orders/${item.id}`}>Xem chi tiết<ChevronRight size={15} /></Link></div></article>) : <Empty text="Chưa có đơn hàng phù hợp" />}</>;
}
function Favorites() {
  const [items, setItems] = useState(demoOrders);
  const [search, setSearch] = useState("");
  const filtered = items.filter((item) => item.name.toLowerCase().includes(search.toLowerCase()));
  return <><label className="account-search"><Search size={19} /><input aria-label="Tìm sản phẩm yêu thích" placeholder="Tìm trong sản phẩm yêu thích" value={search} onChange={(event) => setSearch(event.target.value)} /></label><p className="account-muted">{items.length} sản phẩm đã yêu thích</p>
    {filtered.length ? <div className="account-favorite-grid">{filtered.map((item) => <article className="account-favorite" key={item.id}><div className="account-favorite-art"><ProductIcon kind={item.kind} size={72} /><button type="button" aria-label={`Bỏ yêu thích ${item.name}`} onClick={() => setItems(items.filter((value) => value.id !== item.id))}><Heart size={20} fill="currentColor" /></button></div><h2>{item.name}</h2><strong>{displayMoney(item.price)}</strong><Link href="/products" className="account-action secondary">Khám phá sản phẩm</Link></article>)}</div> : <Empty text="Chưa có sản phẩm yêu thích phù hợp" />}</>;
}
type Address = { id: number; name: string; phone: string; address: string; label: string };
function Addresses() {
  const [items, setItems] = useState<Address[]>([
    { id: 1, name: "Nguyễn Văn A", phone: "0987654321", address: "123 Nguyễn Văn Linh, Phường Tân Phong, TP. Hồ Chí Minh", label: "Nhà riêng" },
    { id: 2, name: "Nguyễn Văn A", phone: "0987654321", address: "45 Lê Lợi, Phường Bến Nghé, TP. Hồ Chí Minh", label: "Văn phòng" },
  ]);
  const [primary, setPrimary] = useState(1);
  const [draft, setDraft] = useState<Address | null>(null);
  const [removing, setRemoving] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft) return;
    const exists = items.some((item) => item.id === draft.id);
    setItems(exists ? items.map((item) => item.id === draft.id ? draft : item) : [...items, draft]);
    if (!items.length) setPrimary(draft.id);
    setDraft(null); setMessage(demoNotice);
  }
  return <><div className="account-panel-head"><span className="account-muted">{items.length} địa chỉ đã lưu</span><button className="account-action" type="button" onClick={() => setDraft({ id: Date.now(), name: "", phone: "", address: "", label: "Nhà riêng" })}><Plus size={17} />Thêm địa chỉ</button></div>
    {message && <p role="status" className="account-feedback">{message}</p>}
    {draft && <form className="account-inset account-edit-form" onSubmit={save}><h3>{items.some((item) => item.id === draft.id) ? "Chỉnh sửa địa chỉ" : "Địa chỉ mới"}</h3><div className="account-form-grid"><label>Người nhận<input required autoComplete="name" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></label><label>Số điện thoại<input required type="tel" autoComplete="tel" value={draft.phone} onChange={(e) => setDraft({ ...draft, phone: e.target.value })} /></label></div><label>Địa chỉ đầy đủ<textarea required autoComplete="street-address" value={draft.address} onChange={(e) => setDraft({ ...draft, address: e.target.value })} /></label><label>Loại địa chỉ<select value={draft.label} onChange={(e) => setDraft({ ...draft, label: e.target.value })}><option>Nhà riêng</option><option>Văn phòng</option><option>Khác</option></select></label><div className="account-actions"><button type="button" className="account-action secondary" onClick={() => setDraft(null)}>Hủy</button><button className="account-action" type="submit">Lưu địa chỉ</button></div></form>}
    {items.map((item) => <article className="account-address-card" key={item.id}><div className="account-panel-head"><h2><MapPin size={19} />{item.label}</h2>{primary === item.id && <span className="account-pill">Mặc định</span>}</div><strong>{item.name} <span className="account-muted">· {item.phone}</span></strong><p>{item.address}</p><div className="account-actions">{primary !== item.id && <button className="account-text-button" type="button" onClick={() => { setPrimary(item.id); setMessage(demoNotice); }}>Đặt làm mặc định</button>}<button className="account-text-button" type="button" onClick={() => setDraft(item)}><Pencil size={15} />Chỉnh sửa</button><button className="account-text-button danger" type="button" onClick={() => setRemoving(item.id)}><Trash2 size={15} />Xóa</button></div>{removing === item.id && <div className="account-info-note" role="alert">Xóa địa chỉ này?<div className="account-actions"><button type="button" className="account-action secondary" onClick={() => setRemoving(null)}>Giữ lại</button><button type="button" className="account-action" onClick={() => { const next = items.filter((value) => value.id !== item.id); setItems(next); if (primary === item.id) setPrimary(next[0]?.id ?? 0); setRemoving(null); setMessage(demoNotice); }}>Xác nhận xóa</button></div></div>}</article>)}
    {!items.length && !draft && <div className="account-empty"><MapPin size={42} /><h2>Chưa có địa chỉ nhận hàng</h2><p>Thêm địa chỉ để thuận tiện khi đặt hàng.</p></div>}</>;
}
function Notifications() {
  const [items, setItems] = useState([
    { id: 1, title: "Đơn hàng của bạn đang được giao", body: "Đơn DH001234 đang trên đường đến bạn. Xem tiến trình giao hàng trong chi tiết đơn.", date: "Hôm nay, 09:30", read: false, href: "/profile/orders/DH001234", icon: Truck },
    { id: 2, title: "Ưu đãi dành riêng cho hội viên Vàng", body: "Khám phá quyền lợi vận chuyển, tích điểm và quà tặng dành cho bạn.", date: "Hôm qua, 14:00", read: false, href: "/profile/membership", icon: Gift },
    { id: 3, title: "Giao hàng thành công", body: "Đơn DH001233 đã giao thành công. Cảm ơn bạn đã mua sắm cùng KDZ.", date: "18/09/2026, 16:20", read: true, href: "/profile/orders/DH001233", icon: Package },
  ]);
  const [unread, setUnread] = useState(false);
  const visible = items.filter((item) => !unread || !item.read);
  return <><div className="account-panel-head"><div className="account-tabs"><button type="button" className={!unread ? "selected" : ""} onClick={() => setUnread(false)}>Tất cả</button><button type="button" className={unread ? "selected" : ""} onClick={() => setUnread(true)}>Chưa đọc ({items.filter((item) => !item.read).length})</button></div><button type="button" className="account-text-button" onClick={() => setItems(items.map((item) => ({ ...item, read: true })))}><CheckCheck size={17} />Đọc tất cả</button></div>
    {visible.map(({ icon: Icon, ...item }) => <article className={`account-notification ${item.read ? "" : "unread"}`} key={item.id}><span className="account-notification-icon"><Icon size={23} /></span><div><h2>{item.title}</h2><p>{item.body}</p><small>{item.date}</small><div className="account-actions"><Link href={item.href} className="account-text-button">Xem chi tiết<ChevronRight size={15} /></Link>{!item.read && <button type="button" className="account-text-button" onClick={() => setItems(items.map((value) => value.id === item.id ? { ...value, read: true } : value))}>Đánh dấu đã đọc</button>}</div></div></article>)}
    {!visible.length && <div className="account-empty"><Bell size={42} /><h2>Bạn đã đọc hết thông báo</h2><p>Thông báo mới sẽ xuất hiện tại đây.</p></div>}</>;
}
function Password() {
  const [visible, setVisible] = useState<Record<string, boolean>>({});
  const [message, setMessage] = useState("");
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const password = String(form.get("newPassword"));
    if (password !== form.get("confirmPassword")) return setMessage("Mật khẩu xác nhận chưa khớp.");
    if (password === form.get("currentPassword")) return setMessage("Mật khẩu mới cần khác mật khẩu hiện tại.");
    setMessage("Thông tin hợp lệ. Đây là bản xem trước, mật khẩu tài khoản chưa được thay đổi.");
    event.currentTarget.reset();
  }
  return <><div className="account-info-note"><ShieldCheck size={22} /><span>Sử dụng mật khẩu riêng cho tài khoản, tối thiểu 8 ký tự.</span></div><form className="account-edit-form" onSubmit={submit}>{[["currentPassword", "Mật khẩu hiện tại"], ["newPassword", "Mật khẩu mới"], ["confirmPassword", "Xác nhận mật khẩu mới"]].map(([name, label]) => <label key={name}>{label}<div className="account-input"><LockKeyhole size={18} /><input name={name} type={visible[name] ? "text" : "password"} autoComplete={name === "currentPassword" ? "current-password" : "new-password"} required minLength={name === "currentPassword" ? 1 : 8} placeholder={label} /><button type="button" className="account-password-eye" aria-label={`${visible[name] ? "\u1ea8n" : "Hi\u1ec7n"} ${label.toLowerCase()}`} aria-pressed={Boolean(visible[name])} onClick={() => setVisible((current) => ({ ...current, [name]: !current[name] }))}>{visible[name] ? <EyeOff size={18} /> : <Eye size={18} />}</button></div></label>)}{message && <p role="status" className="account-feedback">{message}</p>}<button className="account-save" type="submit"><LockKeyhole size={17} />Cập nhật mật khẩu</button></form></>;
}
function SettingsPanel() {
  const [message, setMessage] = useState("");
  return <form onSubmit={(event) => { event.preventDefault(); setMessage(demoNotice); }}><h2 className="account-section-title"><Bell size={19} />Tùy chọn thông báo</h2>{[
    ["Cập nhật đơn hàng", "Nhận thông tin xác nhận và tiến trình giao hàng.", true],
    ["Ưu đãi và khuyến mãi", "Nhận tin về chương trình giảm giá và quà tặng.", true],
    ["Gợi ý sản phẩm", "Khám phá sản phẩm phù hợp với sở thích.", false],
    ["Thông báo qua email", "Nhận bản tin và thông tin tài khoản qua email.", true],
  ].map(([title, description, checked]) => <label className="account-toggle-row" key={String(title)}><span><strong>{title}</strong><small>{description}</small></span><input type="checkbox" role="switch" aria-label={String(title)} defaultChecked={Boolean(checked)} /></label>)}<h2 className="account-section-title account-spaced"><Settings size={19} />Hiển thị</h2><div className="account-edit-form account-form-grid"><label>Ngôn ngữ<select defaultValue="vi"><option value="vi">Tiếng Việt</option><option value="en">English</option></select></label><label>Tiền tệ<select defaultValue="VND"><option>VND</option><option>USD</option></select></label></div>{message && <p className="account-feedback" role="status">{message}</p>}<button className="account-save" type="submit">Lưu cài đặt</button></form>;
}
function Membership() {
  const [message, setMessage] = useState("");
  return <><div className="account-membership-hero"><Crown size={54} /><span>HẠNG THÀNH VIÊN HIỆN TẠI</span><h2>Hội viên Vàng</h2><p>Cảm ơn bạn đã đồng hành cùng KDZ</p></div><div className="account-points"><div><small>Điểm tích lũy</small><strong>1.250 <span>điểm</span></strong></div><div><small>Hạng tiếp theo</small><strong>Bạch Kim</strong></div></div><progress className="account-progress" value={1250} max={2000} aria-label="Tiến trình lên hạng: 1250 trên 2000 điểm" /><p className="account-muted">Cần thêm 750 điểm để đạt hạng Bạch Kim</p><h2 className="account-section-title account-spaced">Đặc quyền của bạn</h2><div className="account-benefit-grid">{[[Truck, "Miễn phí vận chuyển", "Ưu đãi phí giao hàng cho hội viên."], [Gift, "Quà tặng thành viên", "Đổi điểm để nhận quà tặng yêu thích."], [Crown, "Ưu đãi độc quyền", "Khám phá chương trình dành riêng cho hạng Vàng."]].map(([Icon, title, body]) => { const BenefitIcon = Icon as typeof Truck; return <div className="account-inset" key={String(title)}><BenefitIcon size={27} /><h3>{String(title)}</h3><p>{String(body)}</p></div>; })}</div><h2 className="account-section-title account-spaced">Ưu đãi có thể sử dụng</h2><div className="account-voucher"><Gift size={29} /><div><strong>Ưu đãi vận chuyển</strong><p>Mã mẫu: KDZGOLD</p></div><button type="button" className="account-action secondary" onClick={() => setMessage("Đã chọn ưu đãi mẫu KDZGOLD. Chưa áp dụng vào đơn hàng.")}>Chọn ưu đãi</button></div>{message && <p role="status" className="account-feedback">{message}</p>}</>;
}
function Support() {
  const [message, setMessage] = useState("");
  return <><div className="account-info-note"><Headphones size={26} /><span>Chúng tôi có thể giúp gì cho bạn?<br /><small>Chọn chủ đề hoặc để lại nội dung cần hỗ trợ.</small></span></div><div className="account-faq">{[
    ["Theo dõi đơn hàng như thế nào?", "Mở mục Đơn hàng của tôi và chọn Xem chi tiết để xem trạng thái của từng đơn."],
    ["Thay đổi địa chỉ nhận hàng ở đâu?", "Vào Sổ địa chỉ nhận hàng để thêm, chỉnh sửa hoặc chọn địa chỉ mặc định."],
    ["Tìm đặc quyền hội viên ở đâu?", "Mở Đặc quyền hội viên để xem điểm tích lũy và các ưu đãi của hạng thành viên."],
  ].map(([question, answer]) => <details key={question}><summary>{question}</summary><p>{answer}</p></details>)}</div><form className="account-edit-form" onSubmit={(event) => { event.preventDefault(); setMessage("Nội dung đã được nhập trên giao diện mẫu. Chưa gửi yêu cầu đến bộ phận hỗ trợ."); }}><h2 className="account-section-title"><MessageCircle size={20} />Gửi yêu cầu hỗ trợ</h2><label>Chủ đề<select><option>Đơn hàng và giao nhận</option><option>Tài khoản và bảo mật</option><option>Ưu đãi hội viên</option><option>Khác</option></select></label><label>Email liên hệ<input type="email" autoComplete="email" required defaultValue="khachhang@kdzino.vn" /></label><label>Nội dung<textarea required rows={4} placeholder="Mô tả vấn đề bạn cần hỗ trợ…" /></label>{message && <p className="account-feedback" role="status">{message}</p>}<button type="submit" className="account-save">Gửi yêu cầu</button></form></>;
}
export default function AccountSections({ section, orderId }: { section: AccountSection; orderId?: string }) {
  return <section className="account-details account-card account-section-body" aria-labelledby="account-title"><h1 id="account-title">{orderId ? "Chi tiết đơn hàng" : accountSections[section]}</h1><p className="account-subtitle account-demo-label">Dữ liệu minh họa · Bản xem trước giao diện</p>
    {section === "orders" && <Orders orderId={orderId} />}
    {section === "favorites" && <Favorites />}
    {section === "addresses" && <Addresses />}
    {section === "notifications" && <Notifications />}
    {section === "password" && <Password />}
    {section === "settings" && <SettingsPanel />}
    {section === "membership" && <Membership />}
    {section === "support" && <Support />}
  </section>;
}
