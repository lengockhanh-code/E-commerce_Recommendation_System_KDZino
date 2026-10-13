"""Product Service: Searching, Filtering & Fetching Product Metadata"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from backend.src.models.orm import Product, ProductImage, generate_uuid
from backend.src.models.schemas import ProductSummary, ProductListResponse, CategoryBrandResponse, ProductCreate, ProductUpdate
import time
import re
import unicodedata


def remove_vietnamese_accents(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize('NFD', text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != 'Mn')
    return text.replace('đ', 'd').replace('Đ', 'D').lower()


VIETNAMESE_CONCEPT_KEYWORDS = {
    "ao": ["shirt", "tee", "t-shirt", "top", "jacket", "hoodie", "sweater", "blouse", "coat", "polo", "cardigan", "jersey"],
    "giay": ["shoe", "shoes", "sneaker", "sneakers", "sandal", "sandals", "boot", "boots", "heel", "heels", "loafer", "loafers", "footwear"],
    "quan": ["pant", "pants", "jean", "jeans", "short", "shorts", "trouser", "trousers", "legging", "leggings", "jogger", "joggers"],
    "vay": ["dress", "dresses", "skirt", "skirts"],
    "dam": ["dress", "dresses", "gown", "gowns"],
    "sach": ["book", "books", "comic", "comics", "novel", "novels", "manga"],
    "balo": ["backpack", "backpacks", "bag", "bags", "tote"],
    "tui": ["bag", "bags", "tote", "purse", "handbag", "crossbody"],
    "tai nghe": ["headphone", "headphones", "earphone", "earphones", "earbud", "earbuds", "airpod", "airpods", "headset"],
    "dong ho": ["watch", "watches", "smartwatch"],
    "son": ["lipstick", "lipsticks", "lip balm", "lip gloss"],
    "nuoc hoa": ["perfume", "fragrance", "cologne"],
    "my pham": ["makeup", "cosmetic", "cosmetics", "skincare"],
    "dien thoai": ["phone", "smartphone", "iphone", "samsung", "galaxy"],
    "may tinh": ["laptop", "computer", "macbook"],
    "chuot": ["mouse"],
    "ban phim": ["keyboard", "keyboards"],
    "do choi": ["toy", "toys", "figure", "figures", "action figure", "funko", "lego", "plush", "pokemon", "doll"],
}



def product_to_summary(product: Product) -> ProductSummary:
    images = [img.image_url for img in product.images] if product.images else ["/placeholder.svg"]
    return ProductSummary(
        item_id=product.item_id,
        product_id=product.product_id,
        name=product.name or "Sản phẩm MerRec",
        price=float(product.price) if product.price is not None else 0.0,
        original_price=float(product.original_price) if getattr(product, "original_price", None) is not None else None,
        category0=product.category0,
        category1=product.category1,
        category2=product.category2,
        brand=product.brand,
        condition=product.condition,
        size=product.size,
        color=product.color,
        description=getattr(product, "description", None),
        stock=getattr(product, "stock", 100) if getattr(product, "stock", None) is not None else 100,
        sku=getattr(product, "sku", None),
        weight=getattr(product, "weight", None),
        dimensions=getattr(product, "dimensions", None),
        shipper=getattr(product, "shipper", "MerRec Express"),
        is_active=getattr(product, "is_active", True),
        images=images
    )


def get_products(
    db: Session,
    query: Optional[str] = None,
    category: Optional[str] = None,
    brand: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    sort_by: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
) -> ProductListResponse:
    q = db.query(Product)

    if query:
        q_raw = query.strip()
        q_norm = remove_vietnamese_accents(q_raw)

        # Check if query matches a known Vietnamese concept
        concept_terms = None
        for concept_key, terms in VIETNAMESE_CONCEPT_KEYWORDS.items():
            if re.search(r'\b' + re.escape(concept_key) + r'\b', q_norm):
                concept_terms = terms
                break

        is_postgres = False
        try:
            is_postgres = (db.bind.dialect.name == "postgresql") if db.bind else True
        except Exception:
            is_postgres = True

        if is_postgres:
            if concept_terms:
                regex_pat = r'\y(' + '|'.join(re.escape(t) for t in concept_terms) + r')\y'
                q = q.filter(
                    or_(
                        Product.name.op('~*')(regex_pat),
                        Product.category0.op('~*')(regex_pat),
                        Product.category1.op('~*')(regex_pat),
                        Product.brand.op('~*')(regex_pat)
                    )
                )
            elif len(q_raw) <= 3:
                # Short query: enforce exact word boundary to prevent substring collisions (e.g. "ao" in "Paolini")
                regex_pat = r'\y' + re.escape(q_raw) + r'\y'
                q = q.filter(
                    or_(
                        Product.name.op('~*')(regex_pat),
                        Product.category0.op('~*')(regex_pat),
                        Product.category1.op('~*')(regex_pat),
                        Product.brand.op('~*')(regex_pat)
                    )
                )
            else:
                # Longer query: prefix boundary
                regex_pat = r'\y' + re.escape(q_raw)
                q = q.filter(
                    or_(
                        Product.name.op('~*')(regex_pat),
                        Product.category0.op('~*')(regex_pat),
                        Product.category1.op('~*')(regex_pat),
                        Product.brand.op('~*')(regex_pat)
                    )
                )
        else:
            search_pattern = f"%{q_raw}%"
            q = q.filter(
                or_(
                    Product.name.ilike(search_pattern),
                    Product.category0.ilike(search_pattern),
                    Product.category1.ilike(search_pattern),
                    Product.brand.ilike(search_pattern)
                )
            )

    if category:
        q = q.filter(
            or_(
                Product.category0.ilike(f"%{category}%"),
                Product.category1.ilike(f"%{category}%"),
                Product.category2.ilike(f"%{category}%")
            )
        )

    if brand:
        q = q.filter(Product.brand.ilike(f"%{brand}%"))

    if min_price is not None:
        q = q.filter(Product.price >= min_price)

    if max_price is not None:
        q = q.filter(Product.price <= max_price)

    if sort_by == "price_asc":
        q = q.order_by(Product.price.asc())
    elif sort_by == "price_desc":
        q = q.order_by(Product.price.desc())
    elif sort_by == "newest":
        q = q.order_by(Product.created_at.desc())
    elif sort_by == "name_asc":
        q = q.order_by(Product.name.asc())

    total = q.count()
    offset = (page - 1) * page_size
    products_db = q.offset(offset).limit(page_size).all()

    items = [product_to_summary(p) for p in products_db]
    total_pages = max(1, (total + page_size - 1) // page_size)

    return ProductListResponse(
        products=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


def get_product_by_id(db: Session, item_id: str) -> Optional[ProductSummary]:
    product = db.query(Product).filter(Product.item_id == str(item_id)).first()
    if product:
        return product_to_summary(product)

    # Parquet fallback for full 30,000,000 catalog items not yet in PostgreSQL DB
    try:
        import duckdb
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        catalog_path = root / "data" / "processed" / "recommender" / "serving" / "item_catalog_full.parquet"
        if not catalog_path.exists():
            catalog_path = root / "data" / "processed" / "recommender" / "serving" / "item_catalog_preview.parquet"

        if catalog_path.exists():
            con = duckdb.connect()
            row = con.execute(
                f"SELECT * FROM read_parquet('{catalog_path.as_posix()}') WHERE CAST(item_id AS VARCHAR) = '{item_id}' LIMIT 1"
            ).fetchone()
            if row:
                cols = [c[0] for c in con.description]
                r_dict = dict(zip(cols, row))

                # Auto-sync product to PostgreSQL
                try:
                    new_prod = Product(
                        item_id=str(r_dict["item_id"]),
                        product_id=str(r_dict.get("product_id") or r_dict["item_id"]),
                        name=r_dict.get("name") or "Sản phẩm MerRec",
                        price=float(r_dict.get("price") or 0.0),
                        category0=r_dict.get("category0"),
                        category1=r_dict.get("category1"),
                        category2=r_dict.get("category2"),
                        brand=r_dict.get("brand"),
                        condition=r_dict.get("condition"),
                        size=r_dict.get("size"),
                        color=r_dict.get("color"),
                        shipper=r_dict.get("shipper"),
                        is_active=True
                    )
                    db.add(new_prod)
                    db.commit()
                except Exception:
                    db.rollback()

                return ProductSummary(
                    item_id=str(r_dict["item_id"]),
                    product_id=str(r_dict.get("product_id") or r_dict["item_id"]),
                    name=r_dict.get("name") or "Sản phẩm MerRec",
                    price=float(r_dict.get("price") or 0.0),
                    category0=r_dict.get("category0"),
                    category1=r_dict.get("category1"),
                    category2=r_dict.get("category2"),
                    brand=r_dict.get("brand"),
                    condition=r_dict.get("condition"),
                    size=r_dict.get("size"),
                    color=r_dict.get("color"),
                    images=["/placeholder.svg"]
                )
    except Exception:
        pass

    return None


def get_categories_and_brands(db: Session) -> CategoryBrandResponse:
    cats_db = db.query(Product.category0).distinct().filter(Product.category0.isnot(None)).all()
    brands_db = db.query(Product.brand).distinct().filter(Product.brand.isnot(None)).all()

    categories = sorted(list(set(c[0] for c[0] in cats_db if c[0])))
    brands = sorted(list(set(b[0] for b[0] in brands_db if b[0])))

    return CategoryBrandResponse(categories=categories, brands=brands)


def create_product(db: Session, data: ProductCreate) -> ProductSummary:
    item_id = data.sku.strip() if data.sku and data.sku.strip() else f"KDZ-{int(time.time() * 1000)}"
    existing = db.query(Product).filter(Product.item_id == item_id).first()
    if existing:
        item_id = f"KDZ-{int(time.time() * 1000)}"

    product = Product(
        item_id=item_id,
        product_id=item_id,
        name=data.name.strip(),
        price=data.price,
        original_price=data.original_price or data.price,
        category0=data.category0 or "Thời trang",
        category1=data.category1,
        category2=data.category2,
        brand=data.brand.strip() if data.brand else "KDZino Official",
        condition=data.condition or "Mới 100%",
        description=data.description or data.short_description or "",
        stock=data.stock,
        sku=data.sku or item_id,
        weight=data.weight,
        dimensions=data.dimensions,
        shipper=data.shipper or "KDZino Express",
        size=data.size,
        color=data.color,
        is_active=True
    )
    db.add(product)
    db.flush()

    if data.images:
        for idx, img_url in enumerate(data.images):
            if img_url and img_url.strip():
                prod_img = ProductImage(
                    item_id=item_id,
                    image_url=img_url.strip(),
                    source="seller_upload"
                )
                db.add(prod_img)

    db.commit()
    db.refresh(product)
    return product_to_summary(product)


def update_product(db: Session, item_id: str, data: ProductUpdate) -> Optional[ProductSummary]:
    product = db.query(Product).filter(Product.item_id == item_id).first()
    if not product:
        return None

    if data.name is not None:
        product.name = data.name.strip()
    if data.price is not None:
        product.price = data.price
    if data.original_price is not None:
        product.original_price = data.original_price
    if data.category0 is not None:
        product.category0 = data.category0
    if data.category1 is not None:
        product.category1 = data.category1
    if data.category2 is not None:
        product.category2 = data.category2
    if data.brand is not None:
        product.brand = data.brand
    if data.description is not None:
        product.description = data.description
    if data.stock is not None:
        product.stock = data.stock
    if data.sku is not None:
        product.sku = data.sku
    if data.weight is not None:
        product.weight = data.weight
    if data.dimensions is not None:
        product.dimensions = data.dimensions
    if data.shipper is not None:
        product.shipper = data.shipper
    if data.is_active is not None:
        product.is_active = data.is_active

    if data.images is not None:
        db.query(ProductImage).filter(ProductImage.item_id == item_id).delete()
        for img_url in data.images:
            if img_url and img_url.strip():
                prod_img = ProductImage(
                    item_id=item_id,
                    image_url=img_url.strip(),
                    source="seller_upload"
                )
                db.add(prod_img)

    db.commit()
    db.refresh(product)
    return product_to_summary(product)


def delete_product(db: Session, item_id: str) -> bool:
    product = db.query(Product).filter(Product.item_id == item_id).first()
    if not product:
        return False
    product.is_active = False
    db.commit()
    return True

