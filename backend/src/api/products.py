"""Product Catalog API Endpoints"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.src.database.connection import get_db
from backend.src.models.schemas import ProductSummary, ProductListResponse, CategoryBrandResponse
from backend.src.services.product_service import get_products, get_product_by_id, get_categories_and_brands

router = APIRouter(prefix="/products", tags=["Product Catalog"])


@router.get("", response_model=ProductListResponse)
def list_products(
    q: Optional[str] = Query(None, description="Từ khóa tìm kiếm tên/danh mục/thương hiệu"),
    category: Optional[str] = Query(None, description="Lọc theo danh mục sản phẩm"),
    brand: Optional[str] = Query(None, description="Lọc theo thương hiệu"),
    min_price: Optional[float] = Query(None, ge=0.0, description="Giá tối thiểu"),
    max_price: Optional[float] = Query(None, ge=0.0, description="Giá tối đa"),
    sort_by: Optional[str] = Query(None, description="Sắp xếp: 'price_asc', 'price_desc', 'newest', 'name_asc'"),
    page: int = Query(1, ge=1, description="Trang hiển thị"),
    page_size: int = Query(20, ge=1, le=100, description="Số lượng mỗi trang"),
    db: Session = Depends(get_db)
):
    """Tìm kiếm và xem danh sách sản phẩm có phân trang, sắp xếp & bộ lọc"""
    return get_products(
        db, query=q, category=category, brand=brand,
        min_price=min_price, max_price=max_price, sort_by=sort_by, page=page, page_size=page_size
    )


@router.get("/meta/categories-and-brands", response_model=CategoryBrandResponse)
def categories_and_brands(db: Session = Depends(get_db)):
    """Lấy danh sách các danh mục và thương hiệu phục vụ bộ lọc"""
    return get_categories_and_brands(db)


@router.get("/{item_id}", response_model=ProductSummary)
def product_detail(item_id: str, db: Session = Depends(get_db)):
    """Xem thông tin chi tiết một sản phẩm theo item_id"""
    prod = get_product_by_id(db, item_id)
    if not prod:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sản phẩm với mã '{item_id}' không tồn tại"
        )
    return prod
