"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Bell,
  Truck,
  Tag,
  Gift,
  ShieldCheck,
  CheckCheck,
  Mail,
  ArrowRight,
  PackageCheck,
  Sparkles,
} from "lucide-react";
import "./notifications.css";

export interface NotificationItem {
  id: string;
  category: "orders" | "promos" | "system";
  categoryLabel: string;
  title: string;
  snippet: string;
  fullContent: string;
  time: string;
  read: boolean;
  actionUrl?: string;
  actionText?: string;
}

const INITIAL_NOTIFICATIONS: NotificationItem[] = [
  {
    id: "notif-1",
    category: "orders",
    categoryLabel: "Đơn hàng",
    title: "Đơn hàng #KDZ-98241 đã được giao thành công!",
    snippet: "Kiện hàng bàn phím cơ Akko 3087 v2 của bạn đã được giao đến địa chỉ đăng ký.",
    fullContent:
      "Đơn hàng #KDZ-98241 đã được giao thành công vào lúc 14:30 hôm nay. Cảm ơn bạn đã tin tưởng mua sắm tại KDZino Shop!\n\nHãy dành ít phút đánh giá sản phẩm để nhận ngay voucher giảm 10% cho lần mua hàng tiếp theo.",
    time: "14:30",
    read: false,
    actionUrl: "/profile/orders",
    actionText: "Xem chi tiết đơn hàng",
  },
  {
    id: "notif-2",
    category: "promos",
    categoryLabel: "Khuyến mãi",
    title: "Mã giảm 50.000đ dành riêng cho bạn!",
    snippet: "Nhập mã KDZNEW50 cho mọi đơn hàng từ 300.000đ. Thời hạn có hiệu lực trong 3 ngày.",
    fullContent:
      "Chúc mừng bạn nhận được Voucher độc quyền giảm trực tiếp 50.000đ áp dụng cho tất cả sản phẩm linh kiện & phụ kiện gaming.\n\n- Mã voucher: KDZNEW50\n- Áp dụng đơn từ: 300.000đ\n- Hạn sử dụng: 23:59 ngày 30/09/2026",
    time: "09:15",
    read: false,
    actionUrl: "/products",
    actionText: "Dùng mã ngay",
  },
  {
    id: "notif-3",
    category: "orders",
    categoryLabel: "Đơn hàng",
    title: "Đơn hàng #KDZ-98102 đang trên đường vận chuyển",
    snippet: "Tài xế GHN đang giao Chuột Logitech G Pro X Superlight đến cho bạn.",
    fullContent:
      "Đơn hàng #KDZ-98102 đã được xuất kho và đang trong quá trình vận chuyển. Dự kiến giao tới bạn trong ngày hôm nay.",
    time: "Hôm qua",
    read: false,
    actionUrl: "/profile/orders",
    actionText: "Theo dõi hành trình",
  },
  {
    id: "notif-4",
    category: "system",
    categoryLabel: "Hệ thống",
    title: "Cập nhật tính năng: Tìm kiếm ảnh thông minh & Đặt lại mật khẩu",
    snippet: "KDZino vừa nâng cấp trải nghiệm tìm kiếm sản phẩm bằng AI và phiên đăng nhập dài 180 ngày.",
    fullContent:
      "Chúng tôi vừa ra mắt tính năng tự động khớp ảnh sản phẩm chất lượng cao cùng hệ thống đăng nhập dài hạn bảo mật.\n\nCảm ơn bạn đã luôn đồng hành cùng KDZino!",
    time: "24/09",
    read: true,
    actionUrl: "/products",
    actionText: "Khám phá ngay",
  },
  {
    id: "notif-5",
    category: "promos",
    categoryLabel: "Khuyến mãi",
    title: "Siêu Sale Gaming Gear cuối tuần - Giảm tới 40%",
    snippet: "Hàng trăm sản phẩm tai nghe, bàn phím, chuột gaming giảm giá sốc duy nhất tuần này.",
    fullContent:
      "Chương trình Weekend Gaming Sale chính thức khởi động từ thứ 6 đến hết chủ nhật.\n\n- Giảm giá đến 40% cho bàn phím cơ & tai nghe gaming.\n- Miễn phí vận chuyển toàn quốc cho đơn từ 500k.",
    time: "22/09",
    read: true,
    actionUrl: "/products",
    actionText: "Xem khuyến mãi",
  },
  {
    id: "notif-6",
    category: "system",
    categoryLabel: "Hệ thống",
    title: "Bảo mật tài khoản: Đăng nhập từ thiết bị mới",
    snippet: "Tài khoản của bạn vừa được đăng nhập thành công từ Chrome trên Windows.",
    fullContent:
      "Nếu bạn thực hiện hành động này, bạn có thể bỏ qua thông báo. Nếu không phải bạn, vui lòng đổi mật khẩu ngay để bảo vệ tài khoản.",
    time: "20/09",
    read: true,
    actionUrl: "/profile/security",
    actionText: "Đổi mật khẩu",
  },
];

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<NotificationItem[]>(INITIAL_NOTIFICATIONS);
  const [activeTab, setActiveTab] = useState<"all" | "orders" | "promos" | "system">("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const unreadCount = notifications.filter((item) => !item.read).length;

  const filteredNotifications = notifications.filter((item) => {
    if (activeTab === "all") return true;
    return item.category === activeTab;
  });

  const selectedNotification = notifications.find((item) => item.id === selectedId);

  const handleSelectNotification = (id: string) => {
    setSelectedId(id);
    setNotifications((prev) =>
      prev.map((item) => (item.id === id ? { ...item, read: true } : item))
    );
  };

  const handleMarkAllRead = () => {
    setNotifications((prev) => prev.map((item) => ({ ...item, read: true })));
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case "orders":
        return <Truck size={20} />;
      case "promos":
        return <Tag size={20} />;
      case "system":
        return <ShieldCheck size={20} />;
      default:
        return <Bell size={20} />;
    }
  };

  return (
    <div className="notifications-page-wrapper">
      <div className="container-custom">
        {/* BREADCRUMB */}
        <div className="breadcrumb" style={{ marginBottom: "16px" }}>
          <Link href="/">Trang chủ</Link> › <span className="current">Thông báo</span>
        </div>

        {/* PAGE HEADER */}
        <div className="notifications-header-group">
          <div className="notifications-header-title">
            <h1>🔔 Thông báo</h1>
            {unreadCount > 0 && (
              <span className="notifications-unread-count">{unreadCount} mới</span>
            )}
          </div>

          <button
            type="button"
            className="notifications-mark-all-btn"
            onClick={handleMarkAllRead}
          >
            <CheckCheck size={16} />
            Đánh dấu tất cả đã đọc
          </button>
        </div>

        {/* 2-COLUMN MAIN LAYOUT */}
        <div className="notifications-grid">
          {/* LEFT COLUMN: FILTER TABS & NOTIFICATION LIST */}
          <div className="notifications-list-card">
            <div className="notifications-tabs-bar">
              <button
                type="button"
                className={`notifications-tab-item ${activeTab === "all" ? "active" : ""}`}
                onClick={() => setActiveTab("all")}
              >
                Tất cả ({notifications.length})
              </button>
              <button
                type="button"
                className={`notifications-tab-item ${activeTab === "orders" ? "active" : ""}`}
                onClick={() => setActiveTab("orders")}
              >
                Đơn hàng ({notifications.filter((n) => n.category === "orders").length})
              </button>
              <button
                type="button"
                className={`notifications-tab-item ${activeTab === "promos" ? "active" : ""}`}
                onClick={() => setActiveTab("promos")}
              >
                Khuyến mãi ({notifications.filter((n) => n.category === "promos").length})
              </button>
              <button
                type="button"
                className={`notifications-tab-item ${activeTab === "system" ? "active" : ""}`}
                onClick={() => setActiveTab("system")}
              >
                Hệ thống ({notifications.filter((n) => n.category === "system").length})
              </button>
            </div>

            <div className="notifications-items-container">
              {filteredNotifications.length === 0 ? (
                <div style={{ padding: "40px 20px", textAlign: "center", color: "#6b7280" }}>
                  Chưa có thông báo nào trong danh mục này.
                </div>
              ) : (
                filteredNotifications.map((item) => {
                  const isSelected = item.id === selectedId;
                  return (
                    <div
                      key={item.id}
                      className={`notifications-item-card ${isSelected ? "selected" : ""} ${
                        !item.read ? "unread" : ""
                      }`}
                      onClick={() => handleSelectNotification(item.id)}
                    >
                      <div className={`notifications-icon-wrapper ${item.category}`}>
                        {getCategoryIcon(item.category)}
                      </div>

                      <div className="notifications-item-body">
                        <div className="notifications-item-header-row">
                          <span className={`notifications-item-cat-tag ${item.category}`}>
                            {item.categoryLabel}
                          </span>
                          <span className="notifications-item-time">{item.time}</span>
                        </div>
                        <h4 className="notifications-item-title">{item.title}</h4>
                        <p className="notifications-item-snippet">{item.snippet}</p>
                      </div>

                      {!item.read && <div className="notifications-unread-dot" />}
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* RIGHT COLUMN: NOTIFICATION DETAIL OR EMPTY STATE */}
          <div className="notification-detail-card">
            {selectedNotification ? (
              <div className="notification-full-detail">
                <div className="notification-detail-header">
                  <div className={`notifications-icon-wrapper ${selectedNotification.category}`}>
                    {getCategoryIcon(selectedNotification.category)}
                  </div>
                  <div className="notification-detail-title-group">
                    <h2>{selectedNotification.title}</h2>
                    <div className="notification-detail-meta">
                      <span className={`notifications-item-cat-tag ${selectedNotification.category}`}>
                        {selectedNotification.categoryLabel}
                      </span>
                      <span>•</span>
                      <span>Thời gian: {selectedNotification.time}</span>
                    </div>
                  </div>
                </div>

                <div className="notification-detail-body">
                  {selectedNotification.fullContent}
                </div>

                {selectedNotification.actionUrl && (
                  <div className="notification-detail-action">
                    <Link
                      href={selectedNotification.actionUrl}
                      className="notification-action-btn"
                    >
                      {selectedNotification.actionText || "Xem chi tiết"}
                      <ArrowRight size={16} />
                    </Link>
                  </div>
                )}
              </div>
            ) : (
              <div className="notification-empty-detail">
                <div className="notification-empty-icon-circle">
                  <Mail size={36} />
                </div>
                <h3>Chọn một thông báo</h3>
                <p>Nhấn vào một thông báo bên trái để xem chi tiết nội dung thông báo.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
