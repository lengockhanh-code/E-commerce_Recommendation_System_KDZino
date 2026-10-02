export const accountSections = {
  overview: "Thông tin tài khoản",
  orders: "Đơn hàng của tôi",
  favorites: "Sản phẩm yêu thích",
  history: "Lịch sử hoạt động",
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

export const demoActivityHistory = [
  {
    dateGroup: "Hôm nay · 25/09/2026",
    items: [
      {
        id: "act-1",
        time: "10:25",
        type: "view",
        label: "Đã xem sản phẩm",
        title: "Bàn phím cơ KDZ K87 RGB",
        price: 650000,
        image: "/kdz_logo.png",
        kind: "keyboard",
        actionBtnText: "Xem sản phẩm",
        href: "/products",
      },
      {
        id: "act-2",
        time: "09:15",
        type: "cart",
        label: "Đã thêm vào giỏ hàng",
        title: "Tai nghe Bluetooth KDZ TWS Pro",
        price: 299000,
        image: "/kdz_logo.png",
        kind: "headphones",
        actionBtnText: "Xem giỏ hàng",
        href: "/cart",
      },
      {
        id: "act-3",
        time: "08:40",
        type: "favorite",
        label: "Đã yêu thích sản phẩm",
        title: "Giá đỡ laptop nhôm KDZ",
        price: 350000,
        image: "/kdz_logo.png",
        kind: "accessory",
        actionBtnText: "Xem sản phẩm",
        href: "/products",
      },
    ],
  },
  {
    dateGroup: "24/09/2026",
    items: [
      {
        id: "act-4",
        time: "21:10",
        type: "order",
        label: "Đã đặt hàng",
        subLabel: "Mã đơn hàng #DH001234",
        title: "3 sản phẩm",
        price: 1194000,
        isMultipleImages: true,
        images: ["keyboard", "mouse", "headphones"],
        actionBtnText: "Xem đơn hàng",
        href: "/profile/orders/DH001234",
      },
      {
        id: "act-5",
        time: "15:30",
        type: "rating",
        label: "Đã đánh giá sản phẩm",
        title: "Chuột không dây KDZ X1",
        stars: 5,
        kind: "mouse",
        actionBtnText: "Xem đánh giá",
        href: "/products",
      },
      {
        id: "act-6",
        time: "11:05",
        type: "view",
        label: "Đã xem sản phẩm",
        title: "iPhone 16 series chính thức",
        price: 22990000,
        kind: "phone",
        actionBtnText: "Xem sản phẩm",
        href: "/products",
      },
    ],
  },
  {
    dateGroup: "23/09/2026",
    items: [
      {
        id: "act-7",
        time: "19:20",
        type: "favorite",
        label: "Đã yêu thích sản phẩm",
        title: "Bộ đồ chơi mô hình xe",
        price: 312000,
        kind: "toy",
        actionBtnText: "Xem sản phẩm",
        href: "/products",
      },
      {
        id: "act-8",
        time: "14:12",
        type: "view",
        label: "Đã xem sản phẩm",
        title: "Craft precision cutting mat",
        price: 390000,
        kind: "mat",
        actionBtnText: "Xem sản phẩm",
        href: "/products",
      },
    ],
  },
];

export const displayMoney = (value: number) => new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND" }).format(value);
