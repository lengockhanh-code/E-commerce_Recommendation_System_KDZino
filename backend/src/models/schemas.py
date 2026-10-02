"""Pydantic V2 Validation & Serializer Schemas"""

import datetime
from typing import Optional, List, Any, Literal
from pydantic import BaseModel, EmailStr, Field, field_validator
from uuid import UUID


# --- Authentication Schemas ---

class UserRegister(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: Optional[str] = ""
    new_password: str = Field(..., min_length=6, max_length=100)


class GoogleAuthRequest(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    google_id: Optional[str] = None
    id_token: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    full_name: Optional[str] = None
    provider: Optional[str] = "local"


class UserProfile(BaseModel):
    id: str
    email: EmailStr
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: datetime.datetime
    provider: Optional[str] = "local"

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


class PreferencesUpdate(BaseModel):
    categories: List[Literal["tech", "fashion", "home", "beauty", "baby", "sports", "books", "other"]] = Field(max_length=3)

    @field_validator("categories")
    @classmethod
    def unique_categories(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Danh mục không được trùng lặp")
        return value


class PreferencesResponse(BaseModel):
    categories: List[str]
    completed: bool


# --- Product Catalog Schemas ---

class ProductSummary(BaseModel):
    item_id: str
    product_id: Optional[str] = None
    name: str
    price: float
    category0: Optional[str] = None
    category1: Optional[str] = None
    category2: Optional[str] = None
    brand: Optional[str] = None
    condition: Optional[str] = None
    size: Optional[str] = None
    color: Optional[str] = None
    images: List[str] = []

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    products: List[ProductSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class CategoryBrandResponse(BaseModel):
    categories: List[str]
    brands: List[str]


# --- Order Schemas ---

class OrderItemCreate(BaseModel):
    item_id: str
    product_name: str
    quantity: int = Field(1, ge=1)
    unit_price: float = Field(..., ge=0.0)


class OrderCreate(BaseModel):
    full_name: str
    email: EmailStr
    phone: str
    address: str
    city: Optional[str] = ""
    district: Optional[str] = ""
    payment_method: str = "cod"
    shipping_fee: float = 0.0
    items: List[OrderItemCreate]


class OrderItemResponse(BaseModel):
    id: str
    item_id: str
    product_name: str
    quantity: int
    unit_price: float

    class Config:
        from_attributes = True


class OrderResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    full_name: str
    email: str
    phone: str
    address: str
    city: Optional[str] = None
    district: Optional[str] = None
    payment_method: str
    shipping_fee: float
    total_amount: float
    status: str
    created_at: datetime.datetime
    items: List[OrderItemResponse] = []

    class Config:
        from_attributes = True


# --- Recommendation Schemas ---

class RecommendationRequest(BaseModel):
    context: str = "home"  # 'home', 'product_detail', 'cart'
    item_id: Optional[str] = None
    limit: int = Field(10, ge=1, le=50)


class RecommendationResponse(BaseModel):
    recommendations: List[ProductSummary]
    source: str
    algorithm: str


# --- Event Tracking Schemas ---

class EventCreate(BaseModel):
    event_type: Literal["view", "view_item", "click", "like", "unlike", "cart", "add_to_cart", "offer", "buy_start", "buy_comp", "purchase", "order"]
    item_id: str = Field(min_length=1, max_length=100, pattern=r"^\S+$")
    session_id: Optional[UUID] = None
    event_key: Optional[UUID] = None
    source_page: Optional[str] = Field(None, max_length=100)
    recommendation_request_id: Optional[UUID] = None
    position: Optional[int] = Field(None, ge=1, le=50)
    extra_data: Optional[dict] = None

    @field_validator("event_type")
    @classmethod
    def canonical_event(cls, value):
        return {"view_item": "view", "add_to_cart": "cart", "purchase": "buy_comp", "order": "buy_comp"}.get(value, value)


class EventResponse(BaseModel):
    status: str = "success"
    event_id: str


# --- User Address Schemas ---

class AddressCreate(BaseModel):
    recipient_name: str
    phone: str
    address_line: str
    city: Optional[str] = ""
    district: Optional[str] = ""
    is_default: bool = False


class AddressResponse(BaseModel):
    id: str
    recipient_name: str
    phone: str
    address_line: str
    city: Optional[str] = None
    district: Optional[str] = None
    is_default: bool

    class Config:
        from_attributes = True


# --- Admin Dashboard Schemas ---

class AdminStatsResponse(BaseModel):
    total_revenue: float
    total_orders: int
    total_products: int
    total_users: int
    top_selling_products: List[dict] = []
    recent_orders: List[OrderResponse] = []
