-- Add the API's category list to older installations without dropping columns.
-- Apply explicitly after 002; no startup schema changes.
BEGIN;
ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS categories JSON NOT NULL DEFAULT '[]'::json;
COMMIT;
-- Rollback only if this migration added the column (loses category preferences):
-- ALTER TABLE user_preferences DROP COLUMN categories;
