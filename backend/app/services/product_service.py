"""Product Catalog & Search Service"""

from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, desc, asc

from app.config import settings
from app.model.models import Product, ProductImage
from app.model.schemas import ProductOut, CategoryItemOut, BrandItemOut


def format_product_dict(p: Any) -> Dict[str, Any]:
    if isinstance(p, dict):
        item_id = str(p.get("id") or p.get("item_id"))
        return dict(
            id=item_id,
            name=str(p.get("name") or ""),
            price=float(p.get("price") or 0.0),
            originalPrice=float(p.get("originalPrice") or p.get("price") or 0.0),
            discount=int(p.get("discount") or 0),
            rating=float(p.get("rating") or 0.0),
            soldCount=int(p.get("soldCount") or 0),
            image=str(p.get("image") or ""),
            images=p.get("images") or [],
            c0_name=str(p.get("c0_name") or p.get("category0") or ""),
            c0_display=str(p.get("c0_display") or p.get("category0") or ""),
            c1_name=str(p.get("c1_name") or p.get("category1") or ""),
            c2_name=str(p.get("c2_name") or p.get("category2") or ""),
            brand=str(p.get("brand") or ""),
            condition=str(p.get("condition") or ""),
            size=str(p.get("size") or ""),
            color=str(p.get("color") or ""),
            shipper=str(p.get("shipper") or ""),
            inStock=bool(p.get("inStock", True)),
            stockCount=int(p.get("stockCount") or 99),
            stockKnown=bool(p.get("stockKnown", False)),
            description=str(p.get("description") or ""),
            currency="USD",
            source="merrec"
        )

    return dict(
        id=str(p.item_id),
        name=p.name or "",
        price=float(p.price or 0.0),
        originalPrice=float(p.price or 0.0),
        discount=0,
        rating=0.0,
        soldCount=0,
        image="",
        images=[],
        c0_name=p.category0 or "",
        c0_display=p.category0 or "",
        c1_name=p.category1 or "",
        c2_name=p.category2 or "",
        brand=p.brand or "",
        condition=p.condition or "",
        size=p.size or "",
        color=p.color or "",
        shipper=p.shipper or "",
        inStock=bool(p.is_active),
        stockCount=99,
        stockKnown=False,
        description="",
        currency="USD",
        source="merrec"
    )


def list_products(
    db: Session,
    q: Optional[str] = None,
    category: Optional[str] = None,
    brand: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_rating: Optional[float] = None,
    sort: Optional[str] = "popular",
    page: int = 1,
    limit: int = 24
) -> Tuple[int, List[Dict[str, Any]]]:
    db_count = 0
    try:
        if not settings.MERREC_FORCE_PARQUET:
            db_count = db.query(Product).filter(Product.is_active == True).count()
    except Exception:
        db_count = 0

    if db_count > 0:
        query = db.query(Product).filter(Product.is_active == True)

        if q:
            term = f"%{q.strip()}%"
            query = query.filter(
                or_(
                    Product.name.ilike(term),
                    Product.brand.ilike(term),
                    Product.category0.ilike(term),
                    Product.category1.ilike(term)
                )
            )
        if category and category.lower() != "all":
            query = query.filter(Product.category0.ilike(category))
        if brand and brand.lower() != "all":
            query = query.filter(Product.brand.ilike(brand))
        if min_price is not None:
            query = query.filter(Product.price >= min_price)
        if max_price is not None:
            query = query.filter(Product.price <= max_price)

        total = query.count()

        if sort == "price-asc":
            query = query.order_by(asc(Product.price))
        elif sort == "price-desc":
            query = query.order_by(desc(Product.price))
        elif sort == "newest":
            query = query.order_by(desc(Product.last_seen_ts))
        else:
            query = query.order_by(asc(Product.item_id))

        offset = (page - 1) * limit
        items = query.offset(offset).limit(limit).all()
        return total, [format_product_dict(p) for p in items]

    else:
        # DuckDB Parquet fallback
        import sys
        from pathlib import Path
        SCRIPTS_PATH = str(Path(__file__).resolve().parents[3] / "scripts")
        if SCRIPTS_PATH not in sys.path:
            sys.path.insert(0, SCRIPTS_PATH)
        from storefront_catalog import read_catalog_parquet

        all_products = read_catalog_parquet()
        filtered = all_products

        if q:
            term = q.lower().strip()
            filtered = [p for p in filtered if term in p["name"].lower() or term in p["brand"].lower()]
        if category and category.lower() != "all":
            filtered = [p for p in filtered if p["c0_name"].lower() == category.lower()]
        if brand and brand.lower() != "all":
            filtered = [p for p in filtered if p["brand"].lower() == brand.lower()]
        if min_price is not None:
            filtered = [p for p in filtered if p["price"] >= min_price]
        if max_price is not None:
            filtered = [p for p in filtered if p["price"] <= max_price]

        if sort == "price-asc":
            filtered.sort(key=lambda x: x["price"])
        elif sort == "price-desc":
            filtered.sort(key=lambda x: x["price"], reverse=True)

        total = len(filtered)
        start = (page - 1) * limit
        end = start + limit
        return total, [format_product_dict(p) for p in filtered[start:end]]


def get_product_by_id(db: Session, item_id: str) -> Optional[Dict[str, Any]]:
    try:
        p = db.query(Product).filter(Product.item_id == str(item_id), Product.is_active == True).first()
        if p:
            return format_product_dict(p)
    except Exception:
        pass

    import sys
    from pathlib import Path
    SCRIPTS_PATH = str(Path(__file__).resolve().parents[3] / "scripts")
    if SCRIPTS_PATH not in sys.path:
        sys.path.insert(0, SCRIPTS_PATH)
    from storefront_catalog import read_catalog_parquet

    results = read_catalog_parquet(item_id=str(item_id))
    return format_product_dict(results[0]) if results else None
