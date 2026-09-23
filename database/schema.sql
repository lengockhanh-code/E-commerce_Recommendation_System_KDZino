-- TODO: Implement database/schema.sql.
-- ============================================================
-- MERREC E-COMMERCE RECOMMENDER DATABASE
-- PostgreSQL
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- ============================================================
-- 1. USERS
-- Một user dùng chung cho Local + Google
-- ============================================================

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


-- ============================================================
-- 2. AUTH ACCOUNTS
--
-- provider = local  -> password_hash
-- provider = google -> provider_account_id = Google sub
--
-- Một user có thể có đồng thời:
-- local + google
-- ============================================================

CREATE TABLE IF NOT EXISTS auth_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    provider VARCHAR(20) NOT NULL,

    provider_account_id TEXT,
    provider_email VARCHAR(255),

    password_hash TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_auth_provider
        CHECK (provider IN ('local', 'google')),

    CONSTRAINT chk_auth_account_data
        CHECK (
            (
                provider = 'local'
                AND password_hash IS NOT NULL
            )
            OR
            (
                provider = 'google'
                AND provider_account_id IS NOT NULL
            )
        ),

    UNIQUE (user_id, provider),
    UNIQUE (provider, provider_account_id)
);


-- ============================================================
-- 3. AUTH SESSIONS
-- Lưu refresh token sau khi login
-- ============================================================

CREATE TABLE IF NOT EXISTS auth_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    refresh_token_hash TEXT NOT NULL,

    login_method VARCHAR(20) NOT NULL,

    device_info TEXT,
    ip_address INET,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,

    revoked_at TIMESTAMPTZ,

    CONSTRAINT chk_login_method
        CHECK (login_method IN ('local', 'google'))
);


-- ============================================================
-- 4. EMAIL / OTP VERIFICATION
-- ============================================================

CREATE TABLE IF NOT EXISTS verification_codes (
    id BIGSERIAL PRIMARY KEY,

    user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    destination VARCHAR(255) NOT NULL,

    purpose VARCHAR(30) NOT NULL,

    code_hash TEXT NOT NULL,

    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_verification_purpose
        CHECK (
            purpose IN (
                'register',
                'change_email',
                'forgot_password'
            )
        )
);


-- ============================================================
-- 5. PASSWORD RESET
-- Chỉ cần cho Local Account
-- ============================================================

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    token_hash TEXT NOT NULL UNIQUE,

    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
-- 6. PRODUCTS
--
-- Dữ liệu bảng này được import từ:
--
-- item_catalog_full.parquet
--
-- Đây là catalog phục vụ website.
-- ============================================================

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

    -- Không dùng làm feature chính khi train,
    -- nhưng vẫn giữ để hiển thị web.
    size TEXT,
    color TEXT,

    shipper TEXT,

    last_seen_ts TIMESTAMP,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_product_price
        CHECK (price IS NULL OR price >= 0)
);


-- ============================================================
-- 7. PRODUCT IMAGES
--
-- MerRec không có ảnh.
-- Ta resolve ảnh ngoài rồi lưu URL ở đây.
-- ============================================================

CREATE TABLE IF NOT EXISTS product_images (
    id BIGSERIAL PRIMARY KEY,

    item_id TEXT NOT NULL
        REFERENCES products(item_id)
        ON DELETE CASCADE,

    image_url TEXT NOT NULL,

    source TEXT,

    match_score REAL,

    is_primary BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- Mỗi sản phẩm tối đa 1 ảnh primary
CREATE UNIQUE INDEX IF NOT EXISTS uq_product_primary_image
ON product_images(item_id)
WHERE is_primary = TRUE;


-- ============================================================
-- 8. USER ADDRESSES
-- ============================================================

CREATE TABLE IF NOT EXISTS user_addresses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    receiver_name VARCHAR(255) NOT NULL,

    phone VARCHAR(30),

    province VARCHAR(100),
    district VARCHAR(100),
    ward VARCHAR(100),

    address_line TEXT NOT NULL,

    is_default BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- Một user chỉ có 1 địa chỉ mặc định
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_default_address
ON user_addresses(user_id)
WHERE is_default = TRUE;


-- ============================================================
-- 9. USER PREFERENCES
-- Thông tin onboarding user mới
-- ============================================================

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id UUID PRIMARY KEY
        REFERENCES users(id)
        ON DELETE CASCADE,

    min_price DOUBLE PRECISION,
    max_price DOUBLE PRECISION,

    onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_preference_price
        CHECK (
            min_price IS NULL
            OR max_price IS NULL
            OR min_price <= max_price
        )
);


-- ============================================================
-- 10. CATEGORIES USER THÍCH
-- ============================================================

CREATE TABLE IF NOT EXISTS user_preferred_categories (
    user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    category_name TEXT NOT NULL,

    preference_weight REAL NOT NULL DEFAULT 1.0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (
        user_id,
        category_name
    )
);


-- ============================================================
-- 11. BRANDS USER THÍCH
-- ============================================================

CREATE TABLE IF NOT EXISTS user_preferred_brands (
    user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    brand_name TEXT NOT NULL,

    preference_weight REAL NOT NULL DEFAULT 1.0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (
        user_id,
        brand_name
    )
);


-- ============================================================
-- 12. SẢN PHẨM USER CHỌN THÍCH KHI ONBOARDING
--
-- Ví dụ:
-- "Hãy chọn 3-5 sản phẩm bạn thích"
-- ============================================================

CREATE TABLE IF NOT EXISTS user_preferred_items (
    user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    item_id TEXT NOT NULL
        REFERENCES products(item_id)
        ON DELETE CASCADE,

    preference_weight REAL NOT NULL DEFAULT 1.0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (
        user_id,
        item_id
    )
);


-- ============================================================
-- 13. USER BROWSING SESSIONS
--
-- KHÁC auth_sessions.
--
-- auth_sessions = phiên đăng nhập
-- user_sessions = phiên sử dụng / browsing
-- ============================================================

CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID
        REFERENCES users(id)
        ON DELETE SET NULL,

    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,

    device_type VARCHAR(50),

    source VARCHAR(100)
);


-- ============================================================
-- 14. RECOMMENDATION REQUESTS
--
-- Mỗi lần recommender sinh danh sách recommendation
-- thì tạo một request.
-- ============================================================

CREATE TABLE IF NOT EXISTS recommendation_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID
        REFERENCES users(id)
        ON DELETE SET NULL,

    session_id UUID
        REFERENCES user_sessions(id)
        ON DELETE SET NULL,

    -- home
    -- product_detail
    -- cart
    -- post_purchase
    -- category
    context VARCHAR(50) NOT NULL,

    -- Nếu recommend từ một sản phẩm đang xem
    trigger_item_id TEXT
        REFERENCES products(item_id)
        ON DELETE SET NULL,

    model_name VARCHAR(100),

    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
-- 15. RECOMMENDATION ITEMS
--
-- Lưu item nào đã được recommend,
-- rank bao nhiêu và score bao nhiêu.
-- ============================================================

CREATE TABLE IF NOT EXISTS recommendation_items (
    request_id UUID NOT NULL
        REFERENCES recommendation_requests(id)
        ON DELETE CASCADE,

    item_id TEXT NOT NULL
        REFERENCES products(item_id)
        ON DELETE CASCADE,

    rank_position INTEGER NOT NULL,

    score DOUBLE PRECISION,

    source_model VARCHAR(100),

    PRIMARY KEY (
        request_id,
        item_id
    ),

    CONSTRAINT chk_rank_position
        CHECK (rank_position > 0)
);


-- ============================================================
-- 16. USER EVENTS
--
-- Dữ liệu realtime phát sinh từ website.
--
-- Đồng bộ event semantics với MerRec:
--
-- view
-- like
-- cart
-- offer
-- buy_start
-- buy_comp
-- ============================================================

CREATE TABLE IF NOT EXISTS user_events (
    id BIGSERIAL PRIMARY KEY,

    user_id UUID
        REFERENCES users(id)
        ON DELETE SET NULL,

    session_id UUID
        REFERENCES user_sessions(id)
        ON DELETE SET NULL,

    item_id TEXT NOT NULL
        REFERENCES products(item_id)
        ON DELETE CASCADE,

    event_type VARCHAR(30) NOT NULL,

    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    source_page VARCHAR(100),

    -- Nếu hành động xảy ra trên một recommendation
    recommendation_request_id UUID
        REFERENCES recommendation_requests(id)
        ON DELETE SET NULL,

    -- Vị trí sản phẩm khi được recommend
    position INTEGER,

    metadata JSONB,

    CONSTRAINT chk_event_type
        CHECK (
            event_type IN (
                'view',
                'like',
                'cart',
                'offer',
                'buy_start',
                'buy_comp'
            )
        )
);


-- ============================================================
-- 17. FAVORITES / WISHLIST
--
-- user_events lưu lịch sử like.
-- favorites lưu TRẠNG THÁI hiện tại.
-- ============================================================

CREATE TABLE IF NOT EXISTS favorites (
    user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    item_id TEXT NOT NULL
        REFERENCES products(item_id)
        ON DELETE CASCADE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (
        user_id,
        item_id
    )
);


-- ============================================================
-- 18. CARTS
-- ============================================================

CREATE TABLE IF NOT EXISTS carts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    status VARCHAR(20) NOT NULL DEFAULT 'active',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_cart_status
        CHECK (
            status IN (
                'active',
                'checked_out',
                'abandoned'
            )
        )
);


-- Một user chỉ có tối đa một active cart
CREATE UNIQUE INDEX IF NOT EXISTS uq_active_cart_per_user
ON carts(user_id)
WHERE status = 'active';


-- ============================================================
-- 19. CART ITEMS
-- ============================================================

CREATE TABLE IF NOT EXISTS cart_items (
    cart_id UUID NOT NULL
        REFERENCES carts(id)
        ON DELETE CASCADE,

    item_id TEXT NOT NULL
        REFERENCES products(item_id)
        ON DELETE CASCADE,

    quantity INTEGER NOT NULL DEFAULT 1,

    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (
        cart_id,
        item_id
    ),

    CONSTRAINT chk_cart_quantity
        CHECK (quantity > 0)
);


-- ============================================================
-- 20. ORDERS
-- ============================================================

CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL
        REFERENCES users(id),

    status VARCHAR(30) NOT NULL DEFAULT 'pending',

    total_amount DOUBLE PRECISION NOT NULL DEFAULT 0,

    -- Snapshot địa chỉ lúc đặt hàng.
    -- Không phụ thuộc việc user sửa địa chỉ sau này.
    shipping_address JSONB,

    payment_method VARCHAR(50),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_order_status
        CHECK (
            status IN (
                'pending',
                'confirmed',
                'shipping',
                'completed',
                'cancelled'
            )
        ),

    CONSTRAINT chk_order_total
        CHECK (total_amount >= 0)
);


-- ============================================================
-- 21. ORDER ITEMS
--
-- Giá được snapshot tại thời điểm mua.
-- ============================================================

CREATE TABLE IF NOT EXISTS order_items (
    id BIGSERIAL PRIMARY KEY,

    order_id UUID NOT NULL
        REFERENCES orders(id)
        ON DELETE CASCADE,

    item_id TEXT NOT NULL
        REFERENCES products(item_id),

    product_name TEXT,

    quantity INTEGER NOT NULL DEFAULT 1,

    unit_price DOUBLE PRECISION NOT NULL,

    CONSTRAINT chk_order_item_quantity
        CHECK (quantity > 0),

    CONSTRAINT chk_order_item_price
        CHECK (unit_price >= 0)
);


-- ============================================================
-- 22. RECOMMENDATION CACHE
--
-- Cache danh sách top-N.
--
-- cache_key ví dụ:
--
-- user:UUID:home
-- user:UUID:product:12345
-- popular:home
-- ============================================================

CREATE TABLE IF NOT EXISTS recommendation_cache (
    cache_key TEXT PRIMARY KEY,

    user_id UUID
        REFERENCES users(id)
        ON DELETE CASCADE,

    context VARCHAR(50) NOT NULL,

    trigger_item_id TEXT
        REFERENCES products(item_id)
        ON DELETE CASCADE,

    item_ids JSONB NOT NULL,

    scores JSONB,

    model_name VARCHAR(100),

    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    expires_at TIMESTAMPTZ
);


-- ============================================================
-- 23. MODEL REGISTRY
--
-- Quản lý model đang deploy.
-- ============================================================

CREATE TABLE IF NOT EXISTS model_registry (
    id BIGSERIAL PRIMARY KEY,

    model_name VARCHAR(100) NOT NULL,

    model_type VARCHAR(100) NOT NULL,

    version VARCHAR(50) NOT NULL,

    artifact_path TEXT,

    metrics JSONB,

    trained_at TIMESTAMPTZ,

    is_active BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (
        model_name,
        version
    )
);


-- ============================================================
-- INDEXES
-- ============================================================

-- ---------- AUTH ----------

CREATE INDEX IF NOT EXISTS idx_auth_accounts_user
ON auth_accounts(user_id);

CREATE INDEX IF NOT EXISTS idx_auth_provider_account
ON auth_accounts(provider, provider_account_id);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_user
ON auth_sessions(user_id);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_expire
ON auth_sessions(expires_at);


-- ---------- PRODUCTS ----------

CREATE INDEX IF NOT EXISTS idx_products_product_id
ON products(product_id);

CREATE INDEX IF NOT EXISTS idx_products_category0
ON products(category0);

CREATE INDEX IF NOT EXISTS idx_products_category1
ON products(category1);

CREATE INDEX IF NOT EXISTS idx_products_category2
ON products(category2);

CREATE INDEX IF NOT EXISTS idx_products_brand
ON products(brand);

CREATE INDEX IF NOT EXISTS idx_products_price
ON products(price);

CREATE INDEX IF NOT EXISTS idx_products_active
ON products(is_active);


-- ---------- IMAGES ----------

CREATE INDEX IF NOT EXISTS idx_product_images_item
ON product_images(item_id);


-- ---------- PREFERENCES ----------

CREATE INDEX IF NOT EXISTS idx_preferred_category_user
ON user_preferred_categories(user_id);

CREATE INDEX IF NOT EXISTS idx_preferred_brand_user
ON user_preferred_brands(user_id);

CREATE INDEX IF NOT EXISTS idx_preferred_item_user
ON user_preferred_items(user_id);


-- ---------- USER EVENTS ----------

CREATE INDEX IF NOT EXISTS idx_events_user_time
ON user_events(user_id, event_time DESC);

CREATE INDEX IF NOT EXISTS idx_events_session_time
ON user_events(session_id, event_time);

CREATE INDEX IF NOT EXISTS idx_events_item_time
ON user_events(item_id, event_time DESC);

CREATE INDEX IF NOT EXISTS idx_events_type_time
ON user_events(event_type, event_time DESC);


-- ---------- FAVORITES ----------

CREATE INDEX IF NOT EXISTS idx_favorites_user
ON favorites(user_id);


-- ---------- CART ----------

CREATE INDEX IF NOT EXISTS idx_carts_user
ON carts(user_id);

CREATE INDEX IF NOT EXISTS idx_cart_items_item
ON cart_items(item_id);


-- ---------- ORDERS ----------

CREATE INDEX IF NOT EXISTS idx_orders_user_time
ON orders(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_order_items_order
ON order_items(order_id);

CREATE INDEX IF NOT EXISTS idx_order_items_item
ON order_items(item_id);


-- ---------- RECOMMENDATION ----------

CREATE INDEX IF NOT EXISTS idx_rec_requests_user_time
ON recommendation_requests(user_id, generated_at DESC);

CREATE INDEX IF NOT EXISTS idx_rec_requests_trigger
ON recommendation_requests(trigger_item_id);

CREATE INDEX IF NOT EXISTS idx_rec_items_item
ON recommendation_items(item_id);

CREATE INDEX IF NOT EXISTS idx_rec_cache_user
ON recommendation_cache(user_id);

CREATE INDEX IF NOT EXISTS idx_rec_cache_expire
ON recommendation_cache(expires_at);


-- ============================================================
-- UPDATED_AT AUTO TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


DROP TRIGGER IF EXISTS trg_users_updated_at ON users;

CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


DROP TRIGGER IF EXISTS trg_auth_accounts_updated_at
ON auth_accounts;

CREATE TRIGGER trg_auth_accounts_updated_at
BEFORE UPDATE ON auth_accounts
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


DROP TRIGGER IF EXISTS trg_products_updated_at
ON products;

CREATE TRIGGER trg_products_updated_at
BEFORE UPDATE ON products
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


DROP TRIGGER IF EXISTS trg_product_images_updated_at
ON product_images;

CREATE TRIGGER trg_product_images_updated_at
BEFORE UPDATE ON product_images
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


DROP TRIGGER IF EXISTS trg_user_preferences_updated_at
ON user_preferences;

CREATE TRIGGER trg_user_preferences_updated_at
BEFORE UPDATE ON user_preferences
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


DROP TRIGGER IF EXISTS trg_user_addresses_updated_at
ON user_addresses;

CREATE TRIGGER trg_user_addresses_updated_at
BEFORE UPDATE ON user_addresses
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


DROP TRIGGER IF EXISTS trg_carts_updated_at
ON carts;

CREATE TRIGGER trg_carts_updated_at
BEFORE UPDATE ON carts
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


DROP TRIGGER IF EXISTS trg_orders_updated_at
ON orders;

CREATE TRIGGER trg_orders_updated_at
BEFORE UPDATE ON orders
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();