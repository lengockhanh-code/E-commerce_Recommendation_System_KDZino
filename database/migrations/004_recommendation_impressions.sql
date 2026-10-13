-- Support real exposure tracking without converting impressions into views.
-- Explicit migration only; never applied automatically on service startup.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
ALTER TABLE user_events DROP CONSTRAINT IF EXISTS chk_event_type;
ALTER TABLE user_events ADD CONSTRAINT chk_event_type CHECK (
    event_type IN ('impression', 'view', 'click', 'like', 'unlike', 'cart',
                   'offer', 'buy_start', 'buy_comp')
) NOT VALID;
ALTER TABLE user_events VALIDATE CONSTRAINT chk_event_type;
COMMIT;
-- On failure PostgreSQL rolls the transaction back, preserving the old check.
-- Reverting the check later requires handling saved impressions explicitly;
-- do not delete events or recategorize exposures as views to perform rollback.
