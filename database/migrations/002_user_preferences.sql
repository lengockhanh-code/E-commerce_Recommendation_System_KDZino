-- Apply explicitly after 001. No startup migration is performed.
BEGIN;
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    categories JSON NOT NULL DEFAULT '[]'::json,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT user_preferences_categories_array CHECK (
        json_typeof(categories) = 'array' AND json_array_length(categories) <= 3
    )
);
CREATE INDEX IF NOT EXISTS user_events_user_recent_idx ON user_events (user_id, event_time DESC);
CREATE INDEX IF NOT EXISTS user_events_session_recent_idx ON user_events (session_id, event_time DESC);
ALTER TABLE user_events ADD COLUMN IF NOT EXISTS event_key UUID;
CREATE UNIQUE INDEX IF NOT EXISTS user_events_event_key_idx ON user_events (event_key);
ALTER TABLE user_events DROP CONSTRAINT IF EXISTS chk_event_type;
ALTER TABLE user_events ADD CONSTRAINT chk_event_type CHECK (
    event_type IN ('view', 'click', 'like', 'unlike', 'cart', 'offer', 'buy_start', 'buy_comp')
);
COMMIT;
-- Rollback (loses saved preferences): DROP TABLE user_preferences;
