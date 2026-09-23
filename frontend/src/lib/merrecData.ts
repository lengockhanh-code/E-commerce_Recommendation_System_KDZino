import catalogPreview from "./catalog-preview.json";

export interface Product {
  id: string;
  name: string;
  price: number;
  originalPrice: number;
  discount: number;
  badge?: string;
  rating: number;
  soldCount: number;
  image: string;
  images: string[];
  c0_name: string;
  c0_display: string;
  c1_name: string;
  brand: string;
  condition: string;
  size?: string;
  color?: string;
  inStock: boolean;
  stockCount: number;
  description: string;
  currency?: string;
  source?: string;
  stockKnown?: boolean;
  c2_name?: string;
  shipper?: string;
}

export interface CategoryItem {
  id: string;
  c0_name: string;
  name: string;
  icon: string;
  count: number;
}

export interface BrandItem {
  id: string;
  name: string;
  count: number;
}

// MerRec Dataset Categories mapped to Vietnamese Display Names & Icons
export const MERREC_CATEGORIES: CategoryItem[] = [
  { id: "electronics", c0_name: "Electronics", name: "Điện thoại & Thiết bị số", icon: "📱", count: 32240 },
  { id: "women", c0_name: "Women", name: "Thời trang & Phụ kiện Nữ", icon: "👗", count: 175389 },
  { id: "men", c0_name: "Men", name: "Thời trang & Phụ kiện Nam", icon: "👕", count: 45189 },
  { id: "toys", c0_name: "Toys & Collectibles", name: "Đồ chơi & Bộ sưu tập", icon: "🧸", count: 87097 },
  { id: "beauty", c0_name: "Beauty", name: "Mỹ phẩm & Làm đẹp", icon: "💄", count: 30535 },
  { id: "kids", c0_name: "Kids", name: "Đồ chơi & Mẹ & Bé", icon: "🍼", count: 47030 },
  { id: "home", c0_name: "Home", name: "Nhà cửa & Đời sống", icon: "🏠", count: 30247 },
  { id: "sports", c0_name: "Sports & outdoors", name: "Thể thao & Du lịch", icon: "⚽", count: 8192 },
  { id: "vintage", c0_name: "Vintage & collectibles", name: "Đồ cổ & Giày Sneaker", icon: "👟", count: 20183 },
  { id: "books", c0_name: "Books", name: "Sách & Văn phòng phẩm", icon: "📚", count: 8335 },
];

export const MERREC_BRANDS: BrandItem[] = [
  { id: "apple", name: "Apple", count: 320 },
  { id: "nike", name: "Nike", count: 14337 },
  { id: "samsung", name: "Samsung", count: 286 },
  { id: "nintendo", name: "Nintendo", count: 6313 },
  { id: "disney", name: "Disney", count: 8582 },
  { id: "funko", name: "Funko", count: 5836 },
  { id: "lululemon", name: "lululemon athletica", count: 5163 },
  { id: "coach", name: "Coach", count: 4234 },
  { id: "xiaomi", name: "Xiaomi", count: 178 },
  { id: "puma", name: "Puma", count: 1950 },
];

// A small, diverse preview exported from the real MerRec serving catalog.
// Full catalog IDs are also available through /api/products/[id].
export const MERREC_PRODUCTS: Product[] = catalogPreview;

export { formatPrice, formatVND, toVND, USD_TO_VND_RATE } from "./money";
