export function removeVietnameseTones(str: string): string {
  if (!str) return "";
  return str
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase();
}

export function matchesWord(text: string, word: string, exactOnly = false): boolean {
  if (!text || !word) return false;
  const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const regex = exactOnly || word.length <= 3
    ? new RegExp(`(^|[^a-zA-Z0-9])${escaped}([^a-zA-Z0-9]|$)`, "i")
    : new RegExp(`(^|[^a-zA-Z0-9])${escaped}`, "i");
  return regex.test(text);
}

export interface ConceptDefinition {
  terms: string[];
  categories?: string[];
}

export const VIETNAMESE_CONCEPTS: Record<string, ConceptDefinition> = {
  ao: {
    terms: ["shirt", "tee", "t-shirt", "top", "jacket", "hoodie", "sweater", "blouse", "coat", "polo", "cardigan", "jersey", "tank"],
    categories: ["Men", "Women", "Kids", "Tops", "Sweaters", "Jackets", "Athletic apparel"],
  },
  giay: {
    terms: ["shoe", "shoes", "sneaker", "sneakers", "sandal", "sandals", "boot", "boots", "heel", "heels", "loafer", "loafers", "trainer", "trainers", "footwear"],
    categories: ["Shoes", "Men", "Women", "Kids"],
  },
  quan: {
    terms: ["pant", "pants", "jean", "jeans", "short", "shorts", "trouser", "trousers", "legging", "leggings", "jogger", "joggers"],
    categories: ["Men", "Women", "Kids"],
  },
  vay: {
    terms: ["dress", "dresses", "skirt", "skirts"],
    categories: ["Women", "Kids"],
  },
  dam: {
    terms: ["dress", "dresses", "gown", "gowns"],
    categories: ["Women", "Kids"],
  },
  sach: {
    terms: ["book", "books", "comic", "comics", "novel", "novels", "manga", "paperback", "hardcover"],
    categories: ["Books"],
  },
  balo: {
    terms: ["backpack", "backpacks", "bag", "bags", "tote"],
  },
  tui: {
    terms: ["bag", "bags", "tote", "purse", "handbag", "crossbody", "wallet"],
  },
  "tai nghe": {
    terms: ["headphone", "headphones", "earphone", "earphones", "earbud", "earbuds", "airpod", "airpods", "headset"],
    categories: ["Electronics"],
  },
  "dong ho": {
    terms: ["watch", "watches", "smartwatch"],
    categories: ["Electronics", "Men", "Women"],
  },
  son: {
    terms: ["lipstick", "lipsticks", "lip balm", "lip gloss", "lip tint"],
    categories: ["Beauty"],
  },
  "nuoc hoa": {
    terms: ["perfume", "fragrance", "cologne"],
    categories: ["Beauty"],
  },
  "my pham": {
    terms: ["makeup", "cosmetic", "cosmetics", "skincare", "skinfinish", "highlighter", "palette", "foundation", "serum", "lotion", "cream"],
    categories: ["Beauty"],
  },
  "dien thoai": {
    terms: ["phone", "smartphone", "iphone", "samsung", "galaxy", "pixel", "cell phone"],
    categories: ["Electronics"],
  },
  "may tinh": {
    terms: ["laptop", "computer", "macbook", "pc"],
    categories: ["Electronics"],
  },
  chuot: {
    terms: ["mouse"],
    categories: ["Electronics"],
  },
  "ban phim": {
    terms: ["keyboard", "keyboards"],
    categories: ["Electronics"],
  },
  "do choi": {
    terms: ["toy", "toys", "figure", "figures", "action figure", "funko", "lego", "plush", "pokemon", "nintendo", "doll"],
    categories: ["Toys & Collectibles"],
  },
};

export const CAT_DISPLAY_MAP: Record<string, string> = {
  Men: "Thời trang Nam",
  Women: "Thời trang Nữ",
  Kids: "Mẹ & Bé",
  Home: "Nhà cửa & Đời sống",
  Electronics: "Điện tử & Công nghệ",
  "Vintage & collectibles": "Đồ cổ & Sưu tầm",
  Beauty: "Làm đẹp & Mỹ phẩm",
  Books: "Sách & Truyện tranh",
  "Sports & outdoors": "Thể thao",
  Handmade: "Thủ công",
  "Toys & Collectibles": "Đồ chơi & Sưu tầm",
};

export function matchProductQuery(
  product: { name: string; brand?: string; c0_name?: string; c1_name?: string; c2_name?: string },
  query: string
): boolean {
  if (!query) return true;
  const clean = query.trim().toLowerCase();
  const normalized = removeVietnameseTones(clean);

  // Check if query matches a concept
  let matchedConcept: ConceptDefinition | null = null;
  for (const [key, concept] of Object.entries(VIETNAMESE_CONCEPTS)) {
    const keyRegex = new RegExp(`(^|[^a-zA-Z0-9])${key}([^a-zA-Z0-9]|$)`, "i");
    if (keyRegex.test(normalized)) {
      matchedConcept = concept;
      break;
    }
  }

  if (matchedConcept) {
    const pName = product.name;
    const pCat1 = product.c1_name || "";
    const pCat2 = product.c2_name || "";
    return matchedConcept.terms.some(
      (t) => matchesWord(pName, t) || matchesWord(pCat1, t) || matchesWord(pCat2, t)
    );
  }

  const words = normalized.split(/\s+/).filter(Boolean);
  const nameNorm = removeVietnameseTones(product.name);
  const brandNorm = removeVietnameseTones(product.brand || "");
  const catNorm = removeVietnameseTones(product.c0_name || "");

  return words.every(
    (w) =>
      matchesWord(nameNorm, w) ||
      matchesWord(brandNorm, w) ||
      matchesWord(catNorm, w)
  );
}
