-- MerRec PostgreSQL Migration 001: Schema & Constraints

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1. PRODUCTS TABLE
CREATE TABLE IF NOT EXISTS products (
    item_id TEXT PRIMARY KEY,
    product_id TEXT,
    name TEXT,
    price DOUBLE PRECISION,
    category0 TEXT,
    category1 TEXT,
    category2 TEXT,
    brand TEXT,
    condition TEXT,
    size TEXT,
    color TEXT,
    shipper TEXT,
    last_seen_ts TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_product_price CHECK (price IS NULL OR price >= 0)
);

CREATE INDEX IF NOT EXISTS idx_products_product_id ON products(product_id);
CREATE INDEX IF NOT EXISTS idx_products_category0 ON products(category0);
CREATE INDEX IF NOT EXISTS idx_products_category1 ON products(category1);
CREATE INDEX IF NOT EXISTS idx_products_category2 ON products(category2);
CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand);
CREATE INDEX IF NOT EXISTS idx_products_price ON products(price);
CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active);

-- 2. PRODUCT IMAGES TABLE
CREATE TABLE IF NOT EXISTS product_images (
    id BIGSERIAL PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES products(item_id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    source TEXT,
    match_score REAL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_product_images_item ON product_images(item_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_product_primary_image
ON product_images(item_id) WHERE is_primary = TRUE;

-- Unique constraint to prevent duplicate (item_id, image_url)
CREATE UNIQUE INDEX IF NOT EXISTS uq_product_images_item_url
ON product_images(item_id, image_url);

-- 3. USERS TABLE
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    username VARCHAR(100) UNIQUE,
    full_name VARCHAR(255),
    avatar_url TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. USER SESSIONS (BROWSING)
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    device_type VARCHAR(50),
    source VARCHAR(100)
);

-- 5. RECOMMENDATION REQUESTS
CREATE TABLE IF NOT EXISTS recommendation_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    session_id UUID REFERENCES user_sessions(id) ON DELETE SET NULL,
    context VARCHAR(50) NOT NULL,
    trigger_item_id TEXT REFERENCES products(item_id) ON DELETE SET NULL,
    model_name VARCHAR(100),
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rec_requests_user_time ON recommendation_requests(user_id, generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_rec_requests_trigger ON recommendation_requests(trigger_item_id);

-- 6. RECOMMENDATION ITEMS
CREATE TABLE IF NOT EXISTS recommendation_items (
    request_id UUID NOT NULL REFERENCES recommendation_requests(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES products(item_id) ON DELETE CASCADE,
    rank_position INTEGER NOT NULL,
    score DOUBLE PRECISION,
    source_model VARCHAR(100),
    PRIMARY KEY (request_id, item_id),
    CONSTRAINT chk_rank_position CHECK (rank_position > 0)
);

CREATE INDEX IF NOT EXISTS idx_rec_items_item ON recommendation_items(item_id);

-- 7. USER EVENTS (INTERACTIONS)
CREATE TABLE IF NOT EXISTS user_events (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    session_id UUID REFERENCES user_sessions(id) ON DELETE SET NULL,
    item_id TEXT NOT NULL REFERENCES products(item_id) ON DELETE CASCADE,
    event_type VARCHAR(30) NOT NULL,
    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_page VARCHAR(100),
    recommendation_request_id UUID REFERENCES recommendation_requests(id) ON DELETE SET NULL,
    position INTEGER,
    metadata JSONB,
    CONSTRAINT chk_event_type CHECK (
        event_type IN ('view', 'like', 'cart', 'offer', 'buy_start', 'buy_comp')
    )
);

CREATE INDEX IF NOT EXISTS idx_events_user_time ON user_events(user_id, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_events_session_time ON user_events(session_id, event_time);
CREATE INDEX IF NOT EXISTS idx_events_item_time ON user_events(item_id, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_events_type_time ON user_events(event_type, event_time DESC);

-- 8. CARTS & CART ITEMS
CREATE TABLE IF NOT EXISTS carts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_cart_status CHECK (status IN ('active', 'checked_out', 'abandoned'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_active_cart_per_user ON carts(user_id) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS cart_items (
    cart_id UUID NOT NULL REFERENCES carts(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES products(item_id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL DEFAULT 1,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (cart_id, item_id),
    CONSTRAINT chk_cart_quantity CHECK (quantity > 0)
);

-- 9. ORDERS & ORDER ITEMS
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    total_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
    shipping_address JSONB,
    payment_method VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_order_status CHECK (
        status IN ('pending', 'confirmed', 'shipping', 'completed', 'cancelled')
    ),
    CONSTRAINT chk_order_total CHECK (total_amount >= 0)
);

CREATE INDEX IF NOT EXISTS idx_orders_user_time ON orders(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS order_items (
    id BIGSERIAL PRIMARY KEY,
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES products(item_id),
    product_name TEXT,
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price DOUBLE PRECISION NOT NULL,
    CONSTRAINT chk_order_item_quantity CHECK (quantity > 0),
    CONSTRAINT chk_order_item_price CHECK (unit_price >= 0)
);

CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_item ON order_items(item_id);

-- 10. RECOMMENDATION CACHE
CREATE TABLE IF NOT EXISTS recommendation_cache (
    cache_key TEXT PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    context VARCHAR(50) NOT NULL,
    trigger_item_id TEXT REFERENCES products(item_id) ON DELETE CASCADE,
    item_ids JSONB NOT NULL,
    scores JSONB,
    model_name VARCHAR(100),
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

-- UPDATED_AT TRIGGER
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_products_updated_at ON products;
CREATE TRIGGER trg_products_updated_at BEFORE UPDATE ON products FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_product_images_updated_at ON product_images;
CREATE TRIGGER trg_product_images_updated_at BEFORE UPDATE ON product_images FOR EACH ROW EXECUTE FUNCTION set_updated_at();
