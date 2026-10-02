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
  { id: "women", c0_name: "Women", name: "Thời trang & Phụ kiện Nữ", icon: "👗", count: 10986847 },
  { id: "toys", c0_name: "Toys & Collectibles", name: "Đồ chơi & Bộ sưu tập", icon: "🧸", count: 5093654 },
  { id: "men", c0_name: "Men", name: "Thời trang & Phụ kiện Nam", icon: "👕", count: 2854161 },
  { id: "kids", c0_name: "Kids", name: "Đồ chơi & Mẹ & Bé", icon: "🍼", count: 2175650 },
  { id: "home", c0_name: "Home", name: "Nhà cửa & Đời sống", icon: "🏠", count: 2063665 },
  { id: "electronics", c0_name: "Electronics", name: "Điện thoại & Thiết bị số", icon: "📱", count: 1692657 },
  { id: "vintage", c0_name: "Vintage & collectibles", name: "Đồ cổ & Sưu tầm", icon: "👟", count: 1549068 },
  { id: "beauty", c0_name: "Beauty", name: "Mỹ phẩm & Làm đẹp", icon: "💄", count: 1510741 },
  { id: "books", c0_name: "Books", name: "Sách & Văn phòng phẩm", icon: "📚", count: 615814 },
  { id: "sports", c0_name: "Sports & outdoors", name: "Thể thao & Du lịch", icon: "⚽", count: 396475 },
  { id: "handmade", c0_name: "Handmade", name: "Thủ công & Handmade", icon: "🎨", count: 275702 },
];

export const MERREC_BRANDS: BrandItem[] = [
  { id: "nike", name: "Nike", count: 756778 },
  { id: "handmade", name: "Handmade", count: 651783 },
  { id: "disney", name: "Disney", count: 561348 },
  { id: "funko", name: "Funko", count: 372163 },
  { id: "pokemon", name: "Pokemon", count: 261341 },
  { id: "nintendo", name: "Nintendo", count: 249553 },
  { id: "lululemon", name: "lululemon athletica", count: 237991 },
  { id: "adidas", name: "Adidas", count: 224098 },
  { id: "panini", name: "Panini", count: 214830 },
  { id: "victorias-secret", name: "Victoria's Secret", count: 205310 },
  { id: "boutique", name: "Boutique", count: 198549 },
  { id: "gildan", name: "Gildan", count: 180857 },
  { id: "coach", name: "Coach", count: 178279 },
  { id: "bts", name: "BTS", count: 161848 },
  { id: "topps", name: "Topps", count: 150715 },
];

// A small, diverse preview exported from the real MerRec serving catalog.
// Full catalog IDs are also available through /api/products/[id].
export const MERREC_PRODUCTS: Product[] = catalogPreview;

export { formatPrice, formatVND, toVND, USD_TO_VND_RATE } from "./money";
