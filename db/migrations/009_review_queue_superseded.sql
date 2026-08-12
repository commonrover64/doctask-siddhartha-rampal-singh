-- a pending register_update item gets superseded (not rejected, that implies a human decided) when a later document
-- disagrees with it before it's ever approved, the disagreement becomes a real conflict item instead of two dangling register_update items
-- for the same field.

ALTER TABLE review_queue DROP CONSTRAINT IF EXISTS review_queue_status_check;
ALTER TABLE review_queue ADD CONSTRAINT review_queue_status_check
    CHECK (status IN ('pending', 'approved', 'rejected', 'superseded'));
    -- superseded = a pending item got folded into a conflict before a human saw it