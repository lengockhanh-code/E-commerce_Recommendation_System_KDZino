"""SQLAlchemy ORM Models mapping to MerRec Schema"""

import datetime
import uuid
from sqlalchemy import (
    Column, String, Text, Float, Boolean, Integer, DateTime, ForeignKey, JSON
)
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.orm import relationship
from backend.src.database.connection import Base


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


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    categories = Column(JSON, nullable=False, default=list)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)


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
    is_active = Column(Boolean, nullable=False, default=True)
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
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")


class ProductImage(Base):
    __tablename__ = "product_images"

    id = Column(GUID(), primary_key=True, default=generate_uuid)
    item_id = Column(String(100), ForeignKey("products.item_id", ondelete="CASCADE"), nullable=False, index=True)
    image_url = Column(Text, nullable=False)
    source = Column(String(50), default="serpapi")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    product = relationship("Product", back_populates="images")


class Order(Base):
    __tablename__ = "orders"

    id = Column(GUID(), primary_key=True, default=generate_uuid)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=False)
    address = Column(Text, nullable=False)
    city = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    payment_method = Column(String(50), default="cod", nullable=False)
    shipping_fee = Column(Float, default=0.0, nullable=False)
    total_amount = Column(Float, nullable=False)
    status = Column(String(50), default="pending", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(GUID(), primary_key=True, default=generate_uuid)
    order_id = Column(GUID(), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(String(100), nullable=False, index=True)
    product_name = Column(Text, nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    unit_price = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    order = relationship("Order", back_populates="items")


class UserAddress(Base):
    __tablename__ = "user_addresses"

    id = Column(GUID(), primary_key=True, default=generate_uuid)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=False)
    address_line = Column(Text, nullable=False)
    city = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="addresses")


class UserSession(Base):
    __tablename__ = "user_sessions"
    id = Column(GUID(), primary_key=True, default=generate_uuid)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    started_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    device_type = Column(String(50), nullable=True)
    source = Column(String(100), nullable=True)


class RecommendationRequest(Base):
    __tablename__ = "recommendation_requests"
    id = Column(GUID(), primary_key=True, default=generate_uuid)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    session_id = Column(GUID(), ForeignKey("user_sessions.id", ondelete="SET NULL"), nullable=True)
    context = Column(String(50), nullable=False)
    trigger_item_id = Column(String(100), ForeignKey("products.item_id", ondelete="SET NULL"), nullable=True)
    model_name = Column(String(100), nullable=True)
    generated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)


class RecommendationItem(Base):
    __tablename__ = "recommendation_items"
    request_id = Column(GUID(), ForeignKey("recommendation_requests.id", ondelete="CASCADE"), primary_key=True)
    item_id = Column(String(100), ForeignKey("products.item_id", ondelete="CASCADE"), primary_key=True)
    rank_position = Column(Integer, nullable=False)
    score = Column(Float, nullable=True)
    source_model = Column(String(100), nullable=True)


class UserEvent(Base):
    __tablename__ = "user_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_key = Column(GUID(), nullable=True, unique=True)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id = Column(GUID(), ForeignKey("user_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    item_id = Column(String(100), ForeignKey("products.item_id", ondelete="CASCADE"), nullable=False, index=True)
    extra_data = Column("metadata", JSON, nullable=True)
    source_page = Column(String(100), nullable=True)
    recommendation_request_id = Column(GUID(), nullable=True)
    position = Column(Integer, nullable=True)
    created_at = Column("event_time", DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)
