"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  ClipboardList,
  Search,
  Check,
  Truck,
  CheckCircle2,
  XCircle,
  MapPin,
  Phone,
  User,
  Package
} from "lucide-react";
import { formatPrice } from "@/lib/merrecData";

interface OrderItem {
  id: string;
  item_id: string;
  product_name: string;
  quantity: number;
  unit_price: number;
}

interface Order {
  id: string;
  full_name: string;
  email: string;
  phone: string;
  address: string;
  payment_method: string;
  total_amount: number;
  status: string;
  created_at: string;
  items: OrderItem[];
}

export default function SellerOrdersPage() {
  return <Suspense fallback={<p role="status">Đang tải đơn hàng…</p>}><SellerOrdersContent /></Suspense>;
}

function SellerOrdersContent() {
  const searchParams = useSearchParams();
  const initialStatus = searchParams.get("status") || "all";

  const [activeTab, setActiveTab] = useState(initialStatus);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [actionMessage, setActionMessage] = useState("");

  const fetchOrders = () => {
    setLoading(true);
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
    let url = `${apiBase}/seller/orders`;
    const params = new URLSearchParams();
    if (activeTab !== "all") params.append("status", activeTab);
    if (search.trim()) params.append("q", search.trim());
    if (params.toString()) url += `?${params.toString()}`;

    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load orders");
        return res.json();
      })
      .then((data: Order[]) => {
        setOrders(data || []);
      })
      .catch((err) => {
        console.warn("Orders fetch fallback:", err);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchOrders();
  }, [activeTab]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchOrders();
  };

  const updateStatus = async (orderId: string, newStatus: string) => {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const res = await fetch(`${apiBase}/seller/orders/${orderId}/status?new_status=${newStatus}`, {
        method: "PATCH"
      });

      if (!res.ok) throw new Error("Không thể cập nhật trạng thái đơn hàng");

      setActionMessage(`Đã cập nhật trạng thái đơn hàng #${orderId.slice(0, 8)} sang "${newStatus}".`);
      fetchOrders();
      setTimeout(() => setActionMessage(""), 4000);
    } catch (err: any) {
      alert(err.message || "Lỗi cập nhật đơn hàng");
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "pending":
        return <span className="seller-status-badge seller-status-pending">● Chờ xác nhận</span>;
      case "confirmed":
        return <span className="seller-status-badge seller-status-shipping">● Chờ lấy hàng</span>;
      case "shipping":
        return <span className="seller-status-badge seller-status-shipping">● Đang giao</span>;
      case "completed":
        return <span className="seller-status-badge seller-status-completed">● Hoàn thành</span>;
      case "cancelled":
        return <span className="seller-status-badge seller-status-cancelled">● Đã hủy</span>;
      default:
        return <span className="seller-status-badge seller-status-pending">{status}</span>;
    }
  };

  return (
    <div className="seller-orders-page">
      {/* HEADER */}
      <div style={{ marginBottom: "20px" }}>
        <h1 style={{ fontSize: "24px", fontWeight: 800, color: "#111827", margin: "0 0 6px 0" }}>
          Quản lý đơn hàng
        </h1>
        <p style={{ fontSize: "13.5px", color: "#6b7280", margin: 0 }}>
          Theo dõi tiến độ, xác nhận và xử lý đơn hàng cho khách hàng nhanh chóng
        </p>
      </div>

      {actionMessage && (
        <div style={{
          padding: "12px 16px",
          background: "#dcfce7",
          border: "1px solid #bbf7d0",
          borderRadius: "8px",
          color: "#166534",
          fontSize: "14px",
          marginBottom: "16px"
        }}>
          {actionMessage}
        </div>
      )}

      {/* TABS & SEARCH */}
      <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: "12px", overflow: "hidden", marginBottom: "20px" }}>
        {/* TABS HEADER */}
        <div style={{
          display: "flex",
          borderBottom: "1px solid #e5e7eb",
          overflowX: "auto",
          background: "#f9fafb"
        }}>
          {[
            { id: "all", label: "Tất cả" },
            { id: "pending", label: "Chờ xác nhận" },
            { id: "confirmed", label: "Chờ lấy hàng" },
            { id: "shipping", label: "Đang giao" },
            { id: "completed", label: "Hoàn thành" },
            { id: "cancelled", label: "Đã hủy" }
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: "14px 20px",
                border: "none",
                background: activeTab === tab.id ? "#ffffff" : "transparent",
                color: activeTab === tab.id ? "#008848" : "#4b5563",
                fontWeight: activeTab === tab.id ? 700 : 500,
                fontSize: "13.5px",
                borderBottom: activeTab === tab.id ? "2px solid #008848" : "none",
                cursor: "pointer",
                whiteSpace: "nowrap"
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* SEARCH BAR */}
        <form onSubmit={handleSearchSubmit} style={{ padding: "16px", display: "flex", gap: "12px" }}>
          <div style={{ position: "relative", flex: 1 }}>
            <input
              type="text"
              placeholder="Tìm theo mã đơn hàng, tên khách hàng, số điện thoại..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="seller-input"
              style={{ paddingLeft: "36px" }}
            />
            <Search size={16} color="#9ca3af" style={{ position: "absolute", left: "12px", top: "12px" }} />
          </div>
          <button type="submit" className="seller-btn-secondary">
            Tìm kiếm
          </button>
        </form>
      </div>

      {/* ORDERS LIST */}
      <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
        {loading ? (
          <div style={{ padding: "40px", textAlign: "center", color: "#6b7280", background: "#ffffff", borderRadius: "12px" }}>
            Đang tải dữ liệu đơn hàng...
          </div>
        ) : orders.length === 0 ? (
          <div style={{ padding: "50px 20px", textAlign: "center", background: "#ffffff", borderRadius: "12px", border: "1px solid #e5e7eb" }}>
            <ClipboardList size={40} color="#9ca3af" style={{ margin: "0 auto 12px auto" }} />
            <p style={{ fontSize: "15px", color: "#4b5563" }}>
              Không có đơn hàng nào trong trạng thái này.
            </p>
          </div>
        ) : (
          orders.map((order) => {
            const itemCount = order.items?.reduce((s, it) => s + (it.quantity || 1), 0) || 1;
            return (
              <div
                key={order.id}
                style={{
                  background: "#ffffff",
                  border: "1px solid #e5e7eb",
                  borderRadius: "12px",
                  padding: "20px",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.03)"
                }}
              >
                {/* ORDER HEADER */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid #f3f4f6", paddingBottom: "12px", marginBottom: "14px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                    <span style={{ fontWeight: 700, fontSize: "14px", color: "#111827" }}>
                      Mã đơn: #{order.id.slice(0, 12)}
                    </span>
                    <span style={{ fontSize: "12px", color: "#6b7280" }}>
                      {new Date(order.created_at).toLocaleString("vi-VN")}
                    </span>
                  </div>
                  <div>{getStatusBadge(order.status)}</div>
                </div>

                {/* ORDER BODY */}
                <div style={{ display: "grid", gridTemplateColumns: "1.8fr 1.2fr", gap: "20px", alignItems: "start" }}>
                  {/* PRODUCTS */}
                  <div>
                    <div style={{ fontSize: "12.5px", fontWeight: 600, color: "#6b7280", marginBottom: "8px" }}>
                      DANH SÁCH SẢN PHẨM ({itemCount})
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                      {order.items?.map((it, idx) => (
                        <div
                          key={idx}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            padding: "8px 12px",
                            background: "#f9fafb",
                            borderRadius: "6px",
                            fontSize: "13px"
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <Package size={16} color="#008848" />
                            <span style={{ fontWeight: 600, color: "#111827" }}>{it.product_name}</span>
                            <span style={{ color: "#6b7280" }}>x{it.quantity}</span>
                          </div>
                          <span style={{ fontWeight: 600, color: "#008848" }}>
                            {formatPrice(it.unit_price * it.quantity)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* CUSTOMER & SHIPPING INFO */}
                  <div style={{ background: "#f9fafb", padding: "14px", borderRadius: "8px", fontSize: "12.5px", color: "#374151" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "6px" }}>
                      <User size={14} color="#6b7280" />
                      <strong>{order.full_name}</strong>
                    </div>
                    {order.phone && (
                      <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "6px" }}>
                        <Phone size={14} color="#6b7280" />
                        <span>{order.phone}</span>
                      </div>
                    )}
                    {order.address && (
                      <div style={{ display: "flex", alignItems: "flex-start", gap: "6px", marginBottom: "8px" }}>
                        <MapPin size={14} color="#6b7280" style={{ flexShrink: 0, marginTop: "2px" }} />
                        <span>{order.address}</span>
                      </div>
                    )}
                    <div style={{ borderTop: "1px solid #e5e7eb", paddingTop: "8px", marginTop: "8px", display: "flex", justifyContent: "space-between" }}>
                      <span>Tổng tiền:</span>
                      <strong style={{ fontSize: "15px", color: "#008848" }}>
                        {formatPrice(order.total_amount)}
                      </strong>
                    </div>
                  </div>
                </div>

                {/* ORDER ACTIONS */}
                <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "16px", paddingTop: "12px", borderTop: "1px solid #f3f4f6" }}>
                  {order.status === "pending" && (
                    <button
                      type="button"
                      onClick={() => updateStatus(order.id, "confirmed")}
                      className="seller-btn-primary"
                      style={{ padding: "8px 16px", fontSize: "13px" }}
                    >
                      <Check size={16} />
                      <span>Xác nhận đơn</span>
                    </button>
                  )}
                  {order.status === "confirmed" && (
                    <button
                      type="button"
                      onClick={() => updateStatus(order.id, "shipping")}
                      className="seller-btn-primary"
                      style={{ padding: "8px 16px", fontSize: "13px" }}
                    >
                      <Truck size={16} />
                      <span>Giao cho ĐVVC</span>
                    </button>
                  )}
                  {order.status === "shipping" && (
                    <button
                      type="button"
                      onClick={() => updateStatus(order.id, "completed")}
                      className="seller-btn-primary"
                      style={{ padding: "8px 16px", fontSize: "13px" }}
                    >
                      <CheckCircle2 size={16} />
                      <span>Đánh dấu hoàn thành</span>
                    </button>
                  )}
                  {order.status !== "completed" && order.status !== "cancelled" && (
                    <button
                      type="button"
                      onClick={() => {
                        if (confirm("Bạn có chắc muốn hủy đơn hàng này?")) {
                          updateStatus(order.id, "cancelled");
                        }
                      }}
                      className="seller-btn-secondary"
                      style={{ padding: "8px 14px", fontSize: "13px", color: "#dc2626", borderColor: "#fecaca" }}
                    >
                      <XCircle size={15} />
                      <span>Hủy đơn</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
