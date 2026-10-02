"use client";

import Link from "next/link";
import { useState, useEffect, type FormEvent } from "react";
import { ArrowRight, Bell, Check, CheckCheck, ChevronLeft, ChevronRight, Crown, Eye, EyeOff, Gift, Headphones, Heart, Keyboard, LockKeyhole, MapPin, MessageCircle, Mouse, Package, Pencil, Plus, Search, Settings, ShieldCheck, ShoppingCart, Star, Trash2, Truck, X } from "lucide-react";
import { accountSections, displayMoney, type AccountSection } from "./account-data";
import { useAuth } from "@/lib/auth-context";
import { getProvinces, getDistricts, getWards } from "@/lib/vietnamLocations";

import ProductImage from "@/components/productcard/ProductImage";
import { formatVND, toVND } from "@/lib/merrecData";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

type ActivityItemAny = Record<string, unknown>;

function ProductIcon({ kind, size = 40 }: { kind?: string; size?: number }) {
  const Icon = kind === "headphones" ? Headphones : kind === "mouse" ? Mouse : Keyboard;
  return <Icon size={size} strokeWidth={1.4} />;
}

function Empty({ text }: { text: string }) {
  return (
    <div className="account-empty">
      <Package size={42} />
      <h2>{text}</h2>
      <p>Hãy khám phá thêm những sản phẩm dành cho bạn.</p>
      <Link className="account-action" href="/products">Khám phá sản phẩm</Link>
    </div>
  );
}

function ActivityHistory({ filterTypes = ["all"] }: { filterTypes?: string[] }) {
  const { token } = useAuth();
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<any[]>([]);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    setLoading(true);
    fetch(`${API_BASE}/profile/history`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (Array.isArray(data)) {
          setItems(data);
        } else {
          setItems([]);
        }
      })
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [token]);

  const filteredItems = items.filter((item) => {
    if (!filterTypes || filterTypes.length === 0 || filterTypes.includes("all")) {
      return true;
    }
    return filterTypes.includes(item.type);
  });

  if (loading) {
    return <div className="account-empty"><p>Đang tải lịch sử hoạt động...</p></div>;
  }

  if (!filteredItems.length) {
    return <Empty text="Chưa có lịch sử hoạt động nào phù hợp" />;
  }

  const groups: { dateGroup: string; items: any[] }[] = [];
  filteredItems.forEach((item) => {
    const dg = item.dateGroup || "Hôm nay";
    let grp = groups.find((g) => g.dateGroup === dg);
    if (!grp) {
      grp = { dateGroup: dg, items: [] };
      groups.push(grp);
    }
    grp.items.push(item);
  });

  return (
    <div className="activity-history-wrapper">
      <div className="activity-timeline-groups">
        {groups.map((group) => (
          <div className="activity-date-group" key={group.dateGroup}>
            <h3 className="activity-date-heading">{group.dateGroup}</h3>

            <div className="activity-items-list">
              {group.items.map((item) => {
                const itemExt = item as ActivityItemAny;
                const priceVnd = item.price > 0 ? (item.price < 5000 ? toVND(item.price) : item.price) : 0;
                return (
                  <div className="activity-item-row" key={item.id}>
                    <div className="activity-item-meta">
                      <span className="activity-time">{item.time}</span>

                      <div className="activity-action-label-box">
                        <strong className="activity-action-label">{item.label}</strong>
                        {Boolean(itemExt.subLabel) && <small className="activity-action-sub">{String(itemExt.subLabel)}</small>}
                      </div>
                    </div>

                    <div className="activity-product-card">
                      <div className="activity-thumb" style={{ width: 50, height: 50, flexShrink: 0, borderRadius: 8, overflow: "hidden" }}>
                        <ProductImage
                          id={item.item_id || item.id}
                          name={item.title}
                          src={item.image && item.image !== "/placeholder.svg" ? item.image : undefined}
                          fit="cover"
                        />
                      </div>

                      <div className="activity-product-details">
                        <span className="activity-product-title">{item.title}</span>
                        {priceVnd > 0 && (
                          <span className="activity-product-price">{formatVND(priceVnd)}</span>
                        )}
                      </div>
                    </div>

                    <Link href={item.href || "/products"} className="activity-btn-action">
                      {item.actionBtnText || "Xem sản phẩm"} <ArrowRight size={14} />
                    </Link>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Orders({ orderId }: { orderId?: string }) {
  const { token } = useAuth();
  const [ordersList, setOrdersList] = useState<any[]>([]);
  const [singleOrder, setSingleOrder] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("Tất cả");
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    setLoading(true);
    if (orderId) {
      fetch(`${API_BASE}/orders/${orderId}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => setSingleOrder(data))
        .catch(() => setSingleOrder(null))
        .finally(() => setLoading(false));
    } else {
      fetch(`${API_BASE}/orders`, {
        headers: { Authorization: `Bearer ${token}` }
      })
        .then((res) => (res.ok ? res.json() : []))
        .then((data) => setOrdersList(Array.isArray(data) ? data : []))
        .catch(() => setOrdersList([]))
        .finally(() => setLoading(false));
    }
  }, [token, orderId]);

  if (loading) {
    return <div className="account-empty"><p>Đang tải danh sách đơn hàng...</p></div>;
  }

  if (orderId && singleOrder) {
    const order = singleOrder;
    const statusText = order.status === "completed" ? "Đã giao" : order.status === "cancelled" ? "Đã hủy" : "Đang giao";
    const statusTone = order.status === "completed" ? "delivered" : order.status === "cancelled" ? "cancelled" : "shipping";

    return (
      <div className="account-order-detail">
        <Link className="account-back" href="/profile/orders">
          <ChevronLeft size={16} />Tất cả đơn hàng
        </Link>
        <div className="account-panel-head">
          <div>
            <h2>Đơn hàng #{order.id.substring(0, 8).toUpperCase()}</h2>
            <p>Đặt ngày {new Date(order.created_at).toLocaleDateString("vi-VN")}</p>
          </div>
          <span className={`account-order-status ${statusTone}`}>{statusText}</span>
        </div>

        {order.status === "cancelled" ? (
          <div className="account-info-note">Đơn hàng đã được hủy. Không có khoản thanh toán cần thực hiện.</div>
        ) : (
          <ol className="account-timeline">
            {["Đã đặt hàng", "Đã xác nhận", "Đang giao", "Đã nhận hàng"].map((step, index) => (
              <li className={index < (order.status === "completed" ? 4 : 3) ? "done" : ""} key={step}>
                <span><Check size={15} /></span>{step}
              </li>
            ))}
          </ol>
        )}

        <div className="account-inset">
          <h3><MapPin size={18} />Địa chỉ nhận hàng</h3>
          <strong>{order.full_name} · {order.phone}</strong>
          <p>{order.address}, {order.district}, {order.city}</p>
        </div>

        {order.items && order.items.map((it: any) => (
          <div className="account-line-product" key={it.id}>
            <span className="account-product-art"><ProductIcon kind="headphones" /></span>
            <div>
              <strong>{it.product_name}</strong>
              <p>Số lượng: {it.quantity}</p>
            </div>
            <strong>{displayMoney(it.unit_price * it.quantity)}</strong>
          </div>
        ))}

        <dl className="account-totals">
          <div><dt>Tạm tính</dt><dd>{displayMoney(order.total_amount - order.shipping_fee)}</dd></div>
          <div><dt>Phí vận chuyển</dt><dd>{displayMoney(order.shipping_fee)}</dd></div>
          <div><dt>Phương thức thanh toán</dt><dd>{order.payment_method === "cod" ? "Thanh toán khi nhận hàng (COD)" : "Chuyển khoản / VNPAY"}</dd></div>
          <div><dt>Tổng cộng</dt><dd>{displayMoney(order.total_amount)}</dd></div>
        </dl>

        <div className="account-actions">
          <Link className="account-action secondary" href="/profile/support">Liên hệ hỗ trợ</Link>
          <Link className="account-action" href="/products">Tiếp tục mua sắm</Link>
        </div>
      </div>
    );
  }

  const mapStatus = (st: string) => (st === "completed" ? "Đã giao" : st === "cancelled" ? "Đã hủy" : "Đang giao");
  const filtered = ordersList.filter((item) => {
    const stLabel = mapStatus(item.status);
    const matchesTab = tab === "Tất cả" || stLabel === tab;
    const matchesSearch = (item.id + (item.items?.[0]?.product_name || "")).toLowerCase().includes(search.toLowerCase());
    return matchesTab && matchesSearch;
  });

  return (
    <>
      <div className="account-tabs" aria-label="Lọc trạng thái đơn hàng">
        {["Tất cả", "Chờ xác nhận", "Đang giao", "Đã giao", "Đã hủy"].map((label) => (
          <button
            type="button"
            aria-pressed={tab === label}
            className={tab === label ? "selected" : ""}
            key={label}
            onClick={() => setTab(label)}
          >
            {label}
          </button>
        ))}
      </div>

      <label className="account-search">
        <Search size={19} />
        <input
          aria-label="Tìm đơn hàng"
          placeholder="Tìm theo mã đơn hoặc tên sản phẩm"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </label>

      {filtered.length ? (
        filtered.map((item) => {
          const stLabel = mapStatus(item.status);
          const tone = item.status === "completed" ? "delivered" : item.status === "cancelled" ? "cancelled" : "shipping";
          const firstItem = item.items?.[0];
          return (
            <article className="account-order-card" key={item.id}>
              <div className="account-panel-head">
                <strong>#{item.id.substring(0, 8).toUpperCase()}<small> · {new Date(item.created_at).toLocaleDateString("vi-VN")}</small></strong>
                <span className={`account-order-status ${tone}`}>{stLabel}</span>
              </div>
              <div className="account-line-product">
                <span className="account-product-art"><ProductIcon kind="headphones" /></span>
                <div>
                  <strong>{firstItem ? firstItem.product_name : "Đơn hàng MerRec"}</strong>
                  <p>Số lượng: {firstItem ? firstItem.quantity : 1}</p>
                </div>
              </div>
              <div className="account-panel-head">
                <span>Thành tiền: <strong>{displayMoney(item.total_amount)}</strong></span>
                <Link className="account-action secondary" href={`/profile/orders/${item.id}`}>
                  Xem chi tiết<ChevronRight size={15} />
                </Link>
              </div>
            </article>
          );
        })
      ) : (
        <Empty text="Chưa có đơn hàng phù hợp" />
      )}
    </>
  );
}

function Favorites() {
  const { token } = useAuth();
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    fetch(`${API_BASE}/profile/history`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (Array.isArray(data)) {
          const favs = data.filter((d) => d.type === "favorite" || d.type === "like");
          setItems(favs);
        }
      })
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) {
    return <div className="account-empty"><p>Đang tải sản phẩm yêu thích...</p></div>;
  }

  const filtered = items.filter((item) => item.title.toLowerCase().includes(search.toLowerCase()));

  return (
    <>
      <label className="account-search">
        <Search size={19} />
        <input
          aria-label="Tìm sản phẩm yêu thích"
          placeholder="Tìm trong sản phẩm yêu thích"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </label>
      <p className="account-muted">{items.length} sản phẩm đã yêu thích</p>

      {filtered.length ? (
        <div className="account-favorite-grid">
          {filtered.map((item) => (
            <article className="account-favorite" key={item.id}>
              <div className="account-favorite-art">
                {item.image && item.image !== "/placeholder.svg" ? (
                  <img src={item.image} alt={item.title} style={{ width: "100%", height: "100%", objectFit: "cover", borderRadius: "6px" }} />
                ) : (
                  <ProductIcon kind="mouse" size={72} />
                )}
                <button
                  type="button"
                  aria-label={`Bỏ yêu thích ${item.title}`}
                  onClick={() => setItems(items.filter((value) => value.id !== item.id))}
                >
                  <Heart size={20} fill="currentColor" />
                </button>
              </div>
              <h2>{item.title}</h2>
              <strong>{displayMoney(item.price)}</strong>
              <Link href={item.href || "/products"} className="account-action secondary">
                Khám phá sản phẩm
              </Link>
            </article>
          ))}
        </div>
      ) : (
        <Empty text="Chưa có sản phẩm yêu thích phù hợp" />
      )}
    </>
  );
}

type Address = { id: string; recipient_name: string; phone: string; address_line: string; city: string; district: string; is_default: boolean };

function Addresses() {
  const { token, user } = useAuth();
  const [items, setItems] = useState<Address[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const [message, setMessage] = useState("");

  // Form states
  const [phone, setPhone] = useState("");
  const [province, setProvince] = useState("Thành phố Hà Nội");
  const [district, setDistrict] = useState("Quận Ba Đình");
  const [ward, setWard] = useState("Phường Phúc Xá");
  const [streetAddress, setStreetAddress] = useState("");
  const [addressType, setAddressType] = useState<"Nhà riêng" | "Văn phòng">("Nhà riêng");
  const [isDefault, setIsDefault] = useState(false);

  const provinces = getProvinces();
  const districts = getDistricts(province);
  const wards = getWards(province, district);

  const loadAddresses = () => {
    if (!token) return;
    fetch(`${API_BASE}/profile/addresses`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setItems(Array.isArray(data) ? data : []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadAddresses();
  }, [token]);

  function openCreateModal() {
    setEditingId(null);
    setPhone("");
    const provs = getProvinces();
    const initialProv = provs[0] || "Thành phố Hà Nội";
    setProvince(initialProv);
    const dists = getDistricts(initialProv);
    const initialDist = dists[0] || "";
    setDistrict(initialDist);
    const wds = getWards(initialProv, initialDist);
    setWard(wds[0] || "");
    setStreetAddress("");
    setAddressType("Nhà riêng");
    setIsDefault(items.length === 0);
    setShowModal(true);
  }

  function openEditModal(item: Address) {
    setEditingId(item.id);
    setPhone(item.phone || "");
    const prov = item.city || "Thành phố Hà Nội";
    setProvince(prov);
    const dists = getDistricts(prov);
    const matchedDist = dists.find((d) => item.district?.includes(d)) || dists[0] || "";
    setDistrict(matchedDist);
    const wds = getWards(prov, matchedDist);
    const matchedWard = wds.find((w) => item.district?.includes(w)) || wds[0] || "";
    setWard(matchedWard);
    setStreetAddress(item.address_line || "");
    setAddressType(item.district?.includes("Văn phòng") ? "Văn phòng" : "Nhà riêng");
    setIsDefault(Boolean(item.is_default));
    setShowModal(true);
  }

  const handleProvinceChange = (newProv: string) => {
    setProvince(newProv);
    const dists = getDistricts(newProv);
    const firstDist = dists[0] || "";
    setDistrict(firstDist);
    const wds = getWards(newProv, firstDist);
    setWard(wds[0] || "");
  };

  const handleDistrictChange = (newDist: string) => {
    setDistrict(newDist);
    const wds = getWards(province, newDist);
    setWard(wds[0] || "");
  };

  async function saveAddress(e: FormEvent) {
    e.preventDefault();
    if (!token) return;

    const formattedDistrict = `${district}, ${ward} (${addressType})`;
    const bodyPayload = {
      recipient_name: user?.full_name || phone.trim() || "Địa chỉ nhận hàng",
      phone: phone.trim(),
      address_line: streetAddress.trim(),
      city: province,
      district: formattedDistrict,
      is_default: isDefault
    };

    try {
      if (editingId) {
        await fetch(`${API_BASE}/profile/addresses/${editingId}`, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` }
        });
      }

      const res = await fetch(`${API_BASE}/profile/addresses`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify(bodyPayload)
      });

      if (!res.ok) throw new Error("Không thể lưu địa chỉ");

      setMessage(editingId ? "Đã cập nhật địa chỉ thành công!" : "Đã lưu địa chỉ mới thành công!");
      setShowModal(false);
      loadAddresses();
    } catch (err: any) {
      setMessage(err.message || "Đã xảy ra lỗi khi lưu địa chỉ");
    }
  }

  async function removeAddress(id: string) {
    if (!token) return;
    try {
      await fetch(`${API_BASE}/profile/addresses/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` }
      });
      setMessage("Đã xóa địa chỉ.");
      setRemoving(null);
      loadAddresses();
    } catch {
      setMessage("Không thể xóa địa chỉ.");
    }
  }

  async function handleSetDefault(item: Address) {
    if (!token || item.is_default) return;
    try {
      await fetch(`${API_BASE}/profile/addresses`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          recipient_name: item.recipient_name || item.phone,
          phone: item.phone,
          address_line: item.address_line,
          city: item.city,
          district: item.district,
          is_default: true
        })
      });
      loadAddresses();
    } catch {
      // silent catch
    }
  }

  if (loading) {
    return <div className="account-empty"><p>Đang tải sổ địa chỉ...</p></div>;
  }

  return (
    <>
      <div className="account-panel-head">
        <span className="account-muted">{items.length} địa chỉ đã lưu</span>
        <button className="shopee-btn-primary" type="button" onClick={openCreateModal}>
          <Plus size={16} /> Thêm địa chỉ mới
        </button>
      </div>

      {message && <p role="status" className="account-feedback">{message}</p>}

      {items.map((item) => {
        const isOffice = item.district?.includes("Văn phòng");
        const typeLabel = isOffice ? "Văn phòng" : "Nhà riêng";
        const cleanDist = item.district?.replace(/ *\([^)]*\) */g, "") || "";
        const fullAddrStr = [item.address_line, cleanDist, item.city].filter(Boolean).join(", ");

        return (
          <article className="shopee-address-card" key={item.id}>
            <div className="shopee-address-left">
              <div className="shopee-address-header">
                <span className="shopee-address-phone">{item.phone}</span>
                {item.is_default && <span className="shopee-badge-default">Mặc định</span>}
                <span className="shopee-badge-type">{typeLabel}</span>
              </div>
              <div className="shopee-address-detail">{fullAddrStr}</div>
            </div>

            <div className="shopee-address-actions">
              <div className="shopee-address-btns">
                <button type="button" className="shopee-text-link" onClick={() => openEditModal(item)}>
                  Cập nhật
                </button>
                <button type="button" className="shopee-text-link danger" onClick={() => setRemoving(item.id)}>
                  Xóa
                </button>
              </div>
              {!item.is_default && (
                <button type="button" className="shopee-btn-set-default" onClick={() => handleSetDefault(item)}>
                  Thiết lập mặc định
                </button>
              )}
            </div>

            {removing === item.id && (
              <div className="account-info-note" style={{ width: "100%", marginTop: "12px" }} role="alert">
                Bạn có chắc chắn muốn xóa địa chỉ này?
                <div className="account-actions">
                  <button type="button" className="account-action secondary" onClick={() => setRemoving(null)}>
                    Giữ lại
                  </button>
                  <button type="button" className="account-action" onClick={() => removeAddress(item.id)}>
                    Xác nhận xóa
                  </button>
                </div>
              </div>
            )}
          </article>
        );
      })}

      {!items.length && !showModal && (
        <div className="account-empty">
          <MapPin size={42} />
          <h2>Chưa có địa chỉ nhận hàng</h2>
          <p>Thêm địa chỉ để nhận hàng thuận tiện hơn.</p>
        </div>
      )}

      {/* SHOPEE ADDRESS MODAL */}
      {showModal && (
        <div className="shopee-modal-backdrop" onClick={(e) => { if (e.target === e.currentTarget) setShowModal(false); }}>
          <div className="shopee-modal-card">
            <div className="shopee-modal-header">
              <h3>{editingId ? "Cập nhật địa chỉ" : "Địa chỉ mới"}</h3>
              <button type="button" className="shopee-modal-close" onClick={() => setShowModal(false)}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={saveAddress}>
              <div className="shopee-modal-body">
                {/* SỐ ĐIỆN THOẠI (BỎ NGƯỜI NHẬN) */}
                <div className="shopee-form-group">
                  <label>Số điện thoại</label>
                  <input
                    type="tel"
                    required
                    placeholder="Nhập số điện thoại nhận hàng"
                    className="shopee-input"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                  />
                </div>

                {/* TỈNH / THÀNH PHỐ, QUẬN / HUYỆN, PHƯỜNG / XÃ */}
                <div className="shopee-form-group">
                  <label>Tỉnh/Thành phố, Quận/Huyện, Phường/Xã</label>
                  <div className="shopee-location-grid">
                    <select
                      className="shopee-select"
                      value={province}
                      onChange={(e) => handleProvinceChange(e.target.value)}
                    >
                      {provinces.map((prov, idx) => (
                        <option key={`prov-${prov}-${idx}`} value={prov}>
                          {prov}
                        </option>
                      ))}
                    </select>

                    <select
                      className="shopee-select"
                      value={district}
                      onChange={(e) => handleDistrictChange(e.target.value)}
                    >
                      {districts.map((dist, idx) => (
                        <option key={`dist-${dist}-${idx}`} value={dist}>
                          {dist}
                        </option>
                      ))}
                    </select>

                    <select
                      className="shopee-select"
                      value={ward}
                      onChange={(e) => setWard(e.target.value)}
                    >
                      {wards.map((wd, idx) => (
                        <option key={`wd-${wd}-${idx}`} value={wd}>
                          {wd}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* ĐỊA CHỈ CỤ THỂ */}
                <div className="shopee-form-group">
                  <label>Địa chỉ cụ thể</label>
                  <textarea
                    required
                    rows={2}
                    placeholder="Số nhà, Tên đường, Tòa nhà, Khu dân cư..."
                    className="shopee-textarea"
                    value={streetAddress}
                    onChange={(e) => setStreetAddress(e.target.value)}
                  />
                </div>

                {/* LOẠI ĐỊA CHỈ */}
                <div className="shopee-form-group">
                  <label>Loại địa chỉ</label>
                  <div className="shopee-type-pills">
                    <button
                      type="button"
                      className={`shopee-pill-btn ${addressType === "Nhà riêng" ? "active" : ""}`}
                      onClick={() => setAddressType("Nhà riêng")}
                    >
                      Nhà Riêng
                    </button>
                    <button
                      type="button"
                      className={`shopee-pill-btn ${addressType === "Văn phòng" ? "active" : ""}`}
                      onClick={() => setAddressType("Văn phòng")}
                    >
                      Văn Phòng
                    </button>
                  </div>
                </div>

                {/* ĐẶT LÀM ĐỊA CHỈ MẶC ĐỊNH */}
                <label className="shopee-checkbox-row">
                  <input
                    type="checkbox"
                    checked={isDefault}
                    onChange={(e) => setIsDefault(e.target.checked)}
                  />
                  <span>Đặt làm địa chỉ mặc định</span>
                </label>
              </div>

              <div className="shopee-modal-footer">
                <button type="button" className="shopee-btn-secondary" onClick={() => setShowModal(false)}>
                  Trở Lại
                </button>
                <button type="submit" className="shopee-btn-primary">
                  Hoàn thành
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}

function Notifications() {
  const [items, setItems] = useState([
    { id: 1, title: "Đơn hàng của bạn đang được giao", body: "Đơn hàng đang trên đường đến bạn. Xem tiến trình giao hàng trong chi tiết đơn.", date: "Hôm nay, 09:30", read: false, href: "/profile/orders", icon: Truck },
    { id: 2, title: "Ưu đãi dành riêng cho hội viên Vàng", body: "Khám phá quyền lợi vận chuyển, tích điểm và quà tặng dành cho bạn.", date: "Hôm qua, 14:00", read: false, href: "/profile/membership", icon: Gift },
    { id: 3, title: "Giao hàng thành công", body: "Đơn hàng đã giao thành công. Cảm ơn bạn đã mua sắm cùng KDZ.", date: "18/09/2026, 16:20", read: true, href: "/profile/orders", icon: Package },
  ]);
  const [unread, setUnread] = useState(false);
  const visible = items.filter((item) => !unread || !item.read);

  return (
    <>
      <div className="account-panel-head">
        <div className="account-tabs">
          <button type="button" className={!unread ? "selected" : ""} onClick={() => setUnread(false)}>Tất cả</button>
          <button type="button" className={unread ? "selected" : ""} onClick={() => setUnread(true)}>Chưa đọc ({items.filter((item) => !item.read).length})</button>
        </div>
        <button type="button" className="account-text-button" onClick={() => setItems(items.map((item) => ({ ...item, read: true })))}>
          <CheckCheck size={17} />Đọc tất cả
        </button>
      </div>
      {visible.map(({ icon: Icon, ...item }) => (
        <article className={`account-notification ${item.read ? "" : "unread"}`} key={item.id}>
          <span className="account-notification-icon"><Icon size={23} /></span>
          <div>
            <h2>{item.title}</h2>
            <p>{item.body}</p>
            <small>{item.date}</small>
            <div className="account-actions">
              <Link href={item.href} className="account-text-button">Xem chi tiết<ChevronRight size={15} /></Link>
              {!item.read && (
                <button type="button" className="account-text-button" onClick={() => setItems(items.map((value) => value.id === item.id ? { ...value, read: true } : value))}>
                  Đánh dấu đã đọc
                </button>
              )}
            </div>
          </div>
        </article>
      ))}
      {!visible.length && (
        <div className="account-empty">
          <Bell size={42} />
          <h2>Bạn đã đọc hết thông báo</h2>
          <p>Thông báo mới sẽ xuất hiện tại đây.</p>
        </div>
      )}
    </>
  );
}

function Password() {
  const { token } = useAuth();
  const [visible, setVisible] = useState<Record<string, boolean>>({});
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const currentPassword = String(form.get("currentPassword") || "");
    const newPassword = String(form.get("newPassword") || "");
    const confirmPassword = String(form.get("confirmPassword") || "");

    if (newPassword !== confirmPassword) {
      return setMessage("Mật khẩu xác nhận chưa khớp.");
    }
    if (currentPassword && newPassword === currentPassword) {
      return setMessage("Mật khẩu mới cần khác mật khẩu hiện tại.");
    }

    if (!token) return;

    setLoading(true);
    setMessage("");
    try {
      const res = await fetch(`${API_BASE}/profile/change-password`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          old_password: currentPassword,
          new_password: newPassword
        })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Không thể cập nhật mật khẩu.");
      }

      setMessage(data.message || "Cập nhật mật khẩu thành công!");
      event.currentTarget.reset();
    } catch (err: any) {
      setMessage(err.message || "Đã xảy ra lỗi.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <div className="account-info-note">
        <ShieldCheck size={22} />
        <span>
          Đổi hoặc tạo mật khẩu riêng cho tài khoản của bạn (tối thiểu 8 ký tự).<br />
          <small className="account-muted">
            Nếu bạn đăng nhập bằng Gmail/Google, bạn có thể bỏ trống <strong>Mật khẩu hiện tại</strong> để tạo mật khẩu riêng lần đầu.
          </small>
        </span>
      </div>
      <form className="account-edit-form" onSubmit={submit}>
        <label key="currentPassword">
          Mật khẩu hiện tại <small className="account-muted">(Bỏ trống nếu tạo mật khẩu lần đầu cho tài khoản Google)</small>
          <div className="account-input">
            <LockKeyhole size={18} />
            <input
              name="currentPassword"
              type={visible.currentPassword ? "text" : "password"}
              autoComplete="current-password"
              placeholder="Mật khẩu hiện tại (nếu có)"
            />
            <button
              type="button"
              className="account-password-eye"
              aria-label={`${visible.currentPassword ? "Ẩn" : "Hiện"} mật khẩu hiện tại`}
              aria-pressed={Boolean(visible.currentPassword)}
              onClick={() => setVisible((current) => ({ ...current, currentPassword: !current.currentPassword }))}
            >
              {visible.currentPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
        </label>

        <label key="newPassword">
          Mật khẩu mới
          <div className="account-input">
            <LockKeyhole size={18} />
            <input
              name="newPassword"
              type={visible.newPassword ? "text" : "password"}
              autoComplete="new-password"
              required
              minLength={8}
              placeholder="Nhập mật khẩu mới (tối thiểu 8 ký tự)"
            />
            <button
              type="button"
              className="account-password-eye"
              aria-label={`${visible.newPassword ? "Ẩn" : "Hiện"} mật khẩu mới`}
              aria-pressed={Boolean(visible.newPassword)}
              onClick={() => setVisible((current) => ({ ...current, newPassword: !current.newPassword }))}
            >
              {visible.newPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
        </label>

        <label key="confirmPassword">
          Xác nhận mật khẩu mới
          <div className="account-input">
            <LockKeyhole size={18} />
            <input
              name="confirmPassword"
              type={visible.confirmPassword ? "text" : "password"}
              autoComplete="new-password"
              required
              minLength={8}
              placeholder="Nhập lại mật khẩu mới"
            />
            <button
              type="button"
              className="account-password-eye"
              aria-label={`${visible.confirmPassword ? "Ẩn" : "Hiện"} xác nhận mật khẩu mới`}
              aria-pressed={Boolean(visible.confirmPassword)}
              onClick={() => setVisible((current) => ({ ...current, confirmPassword: !current.confirmPassword }))}
            >
              {visible.confirmPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
        </label>

        {message && <p role="status" className="account-feedback">{message}</p>}
        <button className="account-save" type="submit" disabled={loading}>
          <LockKeyhole size={17} />
          {loading ? "Đang cập nhật..." : "Cập nhật mật khẩu"}
        </button>
      </form>
    </>
  );
}

function SettingsPanel() {
  const [message, setMessage] = useState("");
  return (
    <form onSubmit={(event) => { event.preventDefault(); setMessage("Đã lưu cài đặt hiển thị."); }}>
      <h2 className="account-section-title"><Bell size={19} />Tùy chọn thông báo</h2>
      {[
        ["Cập nhật đơn hàng", "Nhận thông tin xác nhận và tiến trình giao hàng.", true],
        ["Ưu đãi và khuyến mãi", "Nhận tin về chương trình giảm giá và quà tặng.", true],
        ["Gợi ý sản phẩm", "Khám phá sản phẩm phù hợp với sở thích.", false],
        ["Thông báo qua email", "Nhận bản tin và thông tin tài khoản qua email.", true],
      ].map(([title, description, checked]) => (
        <label className="account-toggle-row" key={String(title)}>
          <span><strong>{title}</strong><small>{description}</small></span>
          <input type="checkbox" role="switch" aria-label={String(title)} defaultChecked={Boolean(checked)} />
        </label>
      ))}
      <h2 className="account-section-title account-spaced"><Settings size={19} />Hiển thị</h2>
      <div className="account-edit-form account-form-grid">
        <label>Ngôn ngữ<select defaultValue="vi"><option value="vi">Tiếng Việt</option><option value="en">English</option></select></label>
        <label>Tiền tệ<select defaultValue="VND"><option>VND</option><option>USD</option></select></label>
      </div>
      {message && <p className="account-feedback" role="status">{message}</p>}
      <button className="account-save" type="submit">Lưu cài đặt</button>
    </form>
  );
}

function Membership() {
  const [message, setMessage] = useState("");
  return (
    <>
      <div className="account-membership-hero">
        <Crown size={54} />
        <span>HẠNG THÀNH VIÊN HIỆN TẠI</span>
        <h2>Hội viên Vàng</h2>
        <p>Cảm ơn bạn đã đồng hành cùng KDZ</p>
      </div>
      <div className="account-points">
        <div><small>Điểm tích lũy</small><strong>1.250 <span>điểm</span></strong></div>
        <div><small>Hạng tiếp theo</small><strong>Bạch Kim</strong></div>
      </div>
      <progress className="account-progress" value={1250} max={2000} aria-label="Tiến trình lên hạng: 1250 trên 2000 điểm" />
      <p className="account-muted">Cần thêm 750 điểm để đạt hạng Bạch Kim</p>
      <h2 className="account-section-title account-spaced">Đặc quyền của bạn</h2>
      <div className="account-benefit-grid">
        {[[Truck, "Miễn phí vận chuyển", "Ưu đãi phí giao hàng cho hội viên."], [Gift, "Quà tặng thành viên", "Đổi điểm để nhận quà tặng yêu thích."], [Crown, "Ưu đãi độc quyền", "Khám phá chương trình dành riêng cho hạng Vàng."]].map(([Icon, title, body]) => {
          const BenefitIcon = Icon as typeof Truck;
          return (
            <div className="account-inset" key={String(title)}>
              <BenefitIcon size={27} />
              <h3>{String(title)}</h3>
              <p>{String(body)}</p>
            </div>
          );
        })}
      </div>
      <h2 className="account-section-title account-spaced">Ưu đãi có thể sử dụng</h2>
      <div className="account-voucher">
        <Gift size={29} />
        <div><strong>Ưu đãi vận chuyển</strong><p>Mã mẫu: KDZGOLD</p></div>
        <button type="button" className="account-action secondary" onClick={() => setMessage("Đã chọn ưu đãi KDZGOLD.")}>Chọn ưu đãi</button>
      </div>
      {message && <p role="status" className="account-feedback">{message}</p>}
    </>
  );
}

function Support() {
  const [message, setMessage] = useState("");
  return (
    <>
      <div className="account-info-note">
        <Headphones size={26} />
        <span>Chúng tôi có thể giúp gì cho bạn?<br /><small>Chọn chủ đề hoặc để lại nội dung cần hỗ trợ.</small></span>
      </div>
      <div className="account-faq">
        {[
          ["Theo dõi đơn hàng như thế nào?", "Mở mục Đơn hàng của tôi và chọn Xem chi tiết để xem trạng thái của từng đơn."],
          ["Thay đổi địa chỉ nhận hàng ở đâu?", "Vào Sổ địa chỉ nhận hàng để thêm, chỉnh sửa hoặc chọn địa chỉ mặc định."],
          ["Tìm đặc quyền hội viên ở đâu?", "Mở Đặc quyền hội viên để xem điểm tích lũy và các ưu đãi của hạng thành viên."],
        ].map(([question, answer]) => (
          <details key={question}>
            <summary>{question}</summary>
            <p>{answer}</p>
          </details>
        ))}
      </div>
      <form className="account-edit-form" onSubmit={(event) => { event.preventDefault(); setMessage("Đã gửi yêu cầu hỗ trợ. Chúng tôi sẽ phản hồi qua email."); }}>
        <h2 className="account-section-title"><MessageCircle size={20} />Gửi yêu cầu hỗ trợ</h2>
        <label>Chủ đề<select><option>Đơn hàng và giao nhận</option><option>Tài khoản và bảo mật</option><option>Ưu đãi hội viên</option><option>Khác</option></select></label>
        <label>Email liên hệ<input type="email" autoComplete="email" required defaultValue="khachhang@kdzino.vn" /></label>
        <label>Nội dung<textarea required rows={4} placeholder="Mô tả vấn đề bạn cần hỗ trợ…" /></label>
        {message && <p className="account-feedback" role="status">{message}</p>}
        <button type="submit" className="account-save">Gửi yêu cầu</button>
      </form>
    </>
  );
}

export default function AccountSections({ section, orderId, filterTypes }: { section: AccountSection; orderId?: string; filterTypes?: string[] }) {
  return (
    <section className="account-details account-card account-section-body" aria-labelledby="account-title">
      <h1 id="account-title">{orderId ? "Chi tiết đơn hàng" : accountSections[section]}</h1>
      {section === "orders" && <Orders orderId={orderId} />}
      {section === "favorites" && <Favorites />}
      {section === "history" && <ActivityHistory filterTypes={filterTypes} />}
      {section === "addresses" && <Addresses />}
      {section === "notifications" && <Notifications />}
      {section === "password" && <Password />}
      {section === "settings" && <SettingsPanel />}
      {section === "membership" && <Membership />}
      {section === "support" && <Support />}
    </section>
  );
}
