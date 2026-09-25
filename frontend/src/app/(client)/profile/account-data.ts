export const accountSections = {
  overview: "Thông tin tài khoản",
  orders: "Đơn hàng của tôi",
  favorites: "Sản phẩm yêu thích",
  addresses: "Sổ địa chỉ nhận hàng",
  notifications: "Thông báo",
  password: "Đổi mật khẩu",
  settings: "Cài đặt",
  membership: "Đặc quyền hội viên",
  support: "Trung tâm hỗ trợ",
  logout: "Đăng xuất",
} as const;
export type AccountSection = keyof typeof accountSections;
export const demoOrders = [
  { id: "DH001234", name: "Tai nghe Bluetooth KDZ", date: "22/09/2026", price: 590000, status: "Đang giao", tone: "shipping", kind: "headphones" },
  { id: "DH001233", name: "Chuột không dây KDZ", date: "18/09/2026", price: 290000, status: "Đã giao", tone: "delivered", kind: "mouse" },
  { id: "DH001232", name: "Bàn phím cơ KDZ", date: "15/09/2026", price: 890000, status: "Đã hủy", tone: "cancelled", kind: "keyboard" },
];
export const displayMoney = (value: number) => new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND" }).format(value);
