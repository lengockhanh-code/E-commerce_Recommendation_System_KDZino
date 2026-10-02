"""Product Service: Searching, Filtering & Fetching Product Metadata"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from backend.src.models.orm import Product, ProductImage
from backend.src.models.schemas import ProductSummary, ProductListResponse, CategoryBrandResponse


def product_to_summary(product: Product) -> ProductSummary:
    images = [img.image_url for img in product.images] if product.images else ["/placeholder.svg"]
    return ProductSummary(
        item_id=product.item_id,
        product_id=product.product_id,
        name=product.name or "Sản phẩm MerRec",
        price=float(product.price) if product.price is not None else 0.0,
        category0=product.category0,
        category1=product.category1,
        category2=product.category2,
        brand=product.brand,
        condition=product.condition,
        size=product.size,
        color=product.color,
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
        search_pattern = f"%{query.strip()}%"
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
