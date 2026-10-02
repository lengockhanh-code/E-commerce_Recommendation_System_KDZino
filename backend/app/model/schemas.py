"""Pydantic Schemas for Request & Response Data Structures"""

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, EmailStr, Field


# ----------------------------------------------------------------------
# 1. AUTH & USER SCHEMAS
# ----------------------------------------------------------------------

class UserRegister(BaseModel):
    full_name: str
    email: EmailStr
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    id_token: Optional[str] = None
    access_token: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    google_id: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    id: str
    email: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool
    is_verified: bool

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)


# ----------------------------------------------------------------------
# 2. PRODUCT & CATALOG SCHEMAS
# ----------------------------------------------------------------------

class ProductImageOut(BaseModel):
    url: str
    source: Optional[str] = None
    title: Optional[str] = None
    score: Optional[float] = None


class ProductOut(BaseModel):
    id: str
    name: Optional[str] = ""
    price: float = 0.0
    originalPrice: float = 0.0
    discount: int = 0
    rating: float = 0.0
    soldCount: int = 0
    image: Optional[str] = ""
    images: List[str] = []
    c0_name: Optional[str] = ""
    c0_display: Optional[str] = ""
    c1_name: Optional[str] = ""
    c2_name: Optional[str] = ""
    brand: Optional[str] = ""
    condition: Optional[str] = ""
    size: Optional[str] = ""
    color: Optional[str] = ""
    shipper: Optional[str] = ""
    inStock: bool = True
    stockCount: int = 99
    stockKnown: bool = False
    description: Optional[str] = ""
    currency: str = "USD"
    source: str = "merrec"
    score: Optional[float] = None

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    total: int
    page: int
    limit: int
    products: List[ProductOut]


class CategoryItemOut(BaseModel):
    id: str
    c0_name: str
    name: str
    icon: str
    count: int


class BrandItemOut(BaseModel):
    id: str
    name: str
    count: int


# ----------------------------------------------------------------------
# 3. RECOMMENDATIONS & EVENTS SCHEMAS
# ----------------------------------------------------------------------

class RecommendationResponse(BaseModel):
    request_id: str
    context: str
    trigger_item_id: Optional[str] = None
    model_name: str
    items: List[ProductOut]


class UserEventCreate(BaseModel):
    item_id: str
    event_type: str  # view, like, cart, offer, buy_start, buy_comp
    source_page: Optional[str] = None
    recommendation_request_id: Optional[str] = None
    position: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


# ----------------------------------------------------------------------
# 4. ORDER SCHEMAS
# ----------------------------------------------------------------------

class OrderItemCreate(BaseModel):
    item_id: str
    product_name: Optional[str] = ""
    quantity: int = Field(1, ge=1)
    unit_price: float = Field(..., ge=0)


class OrderCreate(BaseModel):
    total_amount: float = Field(..., ge=0)
    shipping_address: Optional[Dict[str, Any]] = None
    payment_method: Optional[str] = "cod"
    items: List[OrderItemCreate]


class OrderItemOut(BaseModel):
    id: int
    item_id: str
    product_name: Optional[str] = None
    quantity: int
    unit_price: float

    class Config:
        from_attributes = True


class OrderOut(BaseModel):
    id: str
    user_id: Optional[str] = None
    status: str
    total_amount: float
    shipping_address: Optional[Dict[str, Any]] = None
    payment_method: Optional[str] = None
    created_at: Any
    items: List[OrderItemOut] = []

    class Config:
        from_attributes = True


class OrderStatusUpdate(BaseModel):
    status: str  # pending, confirmed, shipping, completed, cancelled


# ----------------------------------------------------------------------
# 5. ADDRESS & PREFERENCES SCHEMAS
# ----------------------------------------------------------------------

class AddressCreate(BaseModel):
    receiver_name: str
    phone: Optional[str] = None
    province: Optional[str] = None
    district: Optional[str] = None
    ward: Optional[str] = None
    address_line: str
    is_default: bool = False


class AddressOut(BaseModel):
    id: str
    receiver_name: str
    phone: Optional[str] = None
    province: Optional[str] = None
    district: Optional[str] = None
    ward: Optional[str] = None
    address_line: str
    is_default: bool

    class Config:
        from_attributes = True


class UserPreferencesUpdate(BaseModel):
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    preferred_categories: Optional[List[str]] = None
    preferred_brands: Optional[List[str]] = None
    onboarding_completed: bool = True


# ----------------------------------------------------------------------
# 6. ADMIN SCHEMAS
# ----------------------------------------------------------------------

class AdminDashboardStats(BaseModel):
    total_revenue: float
    total_orders: int
    total_products: int
    total_users: int
    recent_sales: List[Dict[str, Any]] = []
