"""Product Catalog API Router"""

import sys
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.model.database import get_db
from app.model.schemas import ProductOut, ProductListResponse, CategoryItemOut, BrandItemOut
from app.services.product_service import list_products, get_product_by_id

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "scripts"))

router = APIRouter(prefix="/products", tags=["Products & Catalog"])


@router.get("", response_model=ProductListResponse)
def get_products(
    q: Optional[str] = Query(None, description="Từ khóa tìm kiếm tên hoặc thương hiệu"),
    category: Optional[str] = Query(None, description="Lọc theo danh mục chính category0"),
    brand: Optional[str] = Query(None, description="Lọc theo thương hiệu"),
    min_price: Optional[float] = Query(None, ge=0, description="Giá tối thiểu"),
    max_price: Optional[float] = Query(None, ge=0, description="Giá tối đa"),
    min_rating: Optional[float] = Query(None, ge=0, le=5, description="Đánh giá từ sao"),
    sort: Optional[str] = Query("popular", description="Sắp xếp: popular, newest, price-asc, price-desc"),
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Lấy danh sách sản phẩm với bộ lọc nâng cao, tìm kiếm và phân trang"""
    total, items = list_products(
        db=db, q=q, category=category, brand=brand,
        min_price=min_price, max_price=max_price, min_rating=min_rating,
        sort=sort, page=page, limit=limit
    )
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "products": items
    }


@router.get("/categories", response_model=List[CategoryItemOut])
def get_categories():
    """Lấy danh sách các danh mục MerRec với biểu tượng và tên hiển thị tiếng Việt"""
    return [
        {"id": "electronics", "c0_name": "Electronics", "name": "Điện thoại & Thiết bị số", "icon": "📱", "count": 32240},
        {"id": "women", "c0_name": "Women", "name": "Thời trang & Phụ kiện Nữ", "icon": "👗", "count": 175389},
        {"id": "men", "c0_name": "Men", "name": "Thời trang & Phụ kiện Nam", "icon": "👕", "count": 45189},
        {"id": "toys", "c0_name": "Toys & Collectibles", "name": "Đồ chơi & Bộ sưu tập", "icon": "🧸", "count": 87097},
        {"id": "beauty", "c0_name": "Beauty", "name": "Mỹ phẩm & Làm đẹp", "icon": "💄", "count": 30535},
        {"id": "kids", "c0_name": "Kids", "name": "Đồ chơi & Mẹ & Bé", "icon": "🍼", "count": 47030},
        {"id": "home", "c0_name": "Home", "name": "Nhà cửa & Đời sống", "icon": "🏠", "count": 30247},
        {"id": "sports", "c0_name": "Sports & outdoors", "name": "Thể thao & Du lịch", "icon": "⚽", "count": 8192},
        {"id": "vintage", "c0_name": "Vintage & collectibles", "name": "Đồ cổ & Giày Sneaker", "icon": "👟", "count": 20183},
        {"id": "books", "c0_name": "Books", "name": "Sách & Văn phòng phẩm", "icon": "📚", "count": 8335},
    ]


@router.get("/brands", response_model=List[BrandItemOut])
def get_brands():
    """Lấy danh sách thương hiệu phổ biến"""
    return [
        {"id": "apple", "name": "Apple", "count": 320},
        {"id": "nike", "name": "Nike", "count": 14337},
        {"id": "samsung", "name": "Samsung", "count": 286},
        {"id": "nintendo", "name": "Nintendo", "count": 6313},
        {"id": "disney", "name": "Disney", "count": 8582},
        {"id": "funko", "name": "Funko", "count": 5836},
        {"id": "lululemon", "name": "lululemon athletica", "count": 5163},
        {"id": "coach", "name": "Coach", "count": 4234},
        {"id": "xiaomi", "name": "Xiaomi", "count": 178},
        {"id": "puma", "name": "Puma", "count": 1950},
    ]


@router.get("/{id}", response_model=ProductOut)
def get_product_detail(id: str, db: Session = Depends(get_db)):
    """Lấy thông tin chi tiết một sản phẩm theo item_id"""
    p = get_product_by_id(db, id)
    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy sản phẩm"
        )
    return p


@router.get("/{id}/images")
def get_product_images_route(id: str, db: Session = Depends(get_db)):
    """Tìm và xác minh ảnh công khai cho sản phẩm"""
    p = get_product_by_id(db, id)
    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy sản phẩm"
        )
    try:
        from storefront_images import resolve_images
        from storefront_catalog import search_images
        images = resolve_images(p, search_images)
        return {"images": images}
    except Exception:
        return {"images": [], "error": "Dịch vụ tìm ảnh đang bận."}
