"""SQLAlchemy ORM Models mapping to MerRec PostgreSQL Schema"""

import datetime
import uuid
from sqlalchemy import (
    Column, String, Text, Float, Boolean, Integer, DateTime, ForeignKey, JSON
)
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.orm import relationship
from app.model.database import Base


class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's native UUID type, otherwise CHAR(36) on SQLite.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID
            return dialect.type_descriptor(PG_UUID(as_uuid=False))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return str(value)


def generate_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=True)
    full_name = Column(String(255), nullable=True)
    avatar_url = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    accounts = relationship("AuthAccount", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="user")
    addresses = relationship("UserAddress", back_populates="user", cascade="all, delete-orphan")


class AuthAccount(Base):
    __tablename__ = "auth_accounts"

    id = Column(GUID(), primary_key=True, default=generate_uuid)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(20), nullable=False)  # 'local', 'google'
    provider_account_id = Column(Text, nullable=True)
    provider_email = Column(String(255), nullable=True)
    password_hash = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="accounts")


class Product(Base):
    __tablename__ = "products"

    item_id = Column(String(100), primary_key=True)
    product_id = Column(String(100), nullable=True, index=True)
    name = Column(Text, nullable=True)
    price = Column(Float, nullable=True, index=True)
    category0 = Column(Text, nullable=True, index=True)
    category1 = Column(Text, nullable=True, index=True)
    category2 = Column(Text, nullable=True, index=True)
    brand = Column(Text, nullable=True, index=True)
    condition = Column(Text, nullable=True)
    size = Column(Text, nullable=True)
    color = Column(Text, nullable=True)
    shipper = Column(Text, nullable=True)
    last_seen_ts = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")


class ProductImage(Base):
    __tablename__ = "product_images"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(String(100), ForeignKey("products.item_id", ondelete="CASCADE"), nullable=False, index=True)
    image_url = Column(Text, nullable=False)
    source = Column(Text, nullable=True)
    match_score = Column(Float, nullable=True)
    is_primary = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    product = relationship("Product", back_populates="images")


class RecommendationRequest(Base):
    __tablename__ = "recommendation_requests"

    id = Column(GUID(), primary_key=True, default=generate_uuid)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id = Column(GUID(), nullable=True)
    context = Column(String(50), nullable=False)
    trigger_item_id = Column(String(100), ForeignKey("products.item_id", ondelete="SET NULL"), nullable=True, index=True)
    model_name = Column(String(100), nullable=True)
    generated_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    rec_items = relationship("RecommendationItem", back_populates="request", cascade="all, delete-orphan")


class RecommendationItem(Base):
    __tablename__ = "recommendation_items"

    request_id = Column(GUID(), ForeignKey("recommendation_requests.id", ondelete="CASCADE"), primary_key=True)
    item_id = Column(String(100), ForeignKey("products.item_id", ondelete="CASCADE"), primary_key=True, index=True)
    rank_position = Column(Integer, nullable=False)
    score = Column(Float, nullable=True)
    source_model = Column(String(100), nullable=True)

    request = relationship("RecommendationRequest", back_populates="rec_items")


class UserEvent(Base):
    __tablename__ = "user_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id = Column(GUID(), nullable=True)
    item_id = Column(String(100), ForeignKey("products.item_id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(30), nullable=False, index=True)  # 'view', 'like', 'cart', 'offer', 'buy_start', 'buy_comp'
    event_time = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    source_page = Column(String(100), nullable=True)
    recommendation_request_id = Column(GUID(), ForeignKey("recommendation_requests.id", ondelete="SET NULL"), nullable=True)
    position = Column(Integer, nullable=True)
    event_metadata = Column("metadata", JSON, nullable=True)


class Favorite(Base):
    __tablename__ = "favorites"

    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    item_id = Column(String(100), ForeignKey("products.item_id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class Order(Base):
    __tablename__ = "orders"

    id = Column(GUID(), primary_key=True, default=generate_uuid)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(30), default="pending", nullable=False)
    total_amount = Column(Float, default=0.0, nullable=False)
    shipping_address = Column(JSON, nullable=True)
    payment_method = Column(String(50), default="cod", nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(GUID(), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(String(100), ForeignKey("products.item_id"), nullable=False, index=True)
    product_name = Column(Text, nullable=True)
    quantity = Column(Integer, default=1, nullable=False)
    unit_price = Column(Float, nullable=False)

    order = relationship("Order", back_populates="items")


class UserAddress(Base):
    __tablename__ = "user_addresses"

    id = Column(GUID(), primary_key=True, default=generate_uuid)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    receiver_name = Column(String(255), nullable=False)
    phone = Column(String(30), nullable=True)
    province = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    ward = Column(String(100), nullable=True)
    address_line = Column(Text, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="addresses")


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    min_price = Column(Float, nullable=True)
    max_price = Column(Float, nullable=True)
    onboarding_completed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
