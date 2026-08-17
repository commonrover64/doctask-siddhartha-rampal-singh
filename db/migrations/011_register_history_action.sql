-- records what decision produced this history row, not just that something changed, needed so the changelog can say "kept new" vs
-- "kept old" vs "set" instead of just "field_name changed"
ALTER TABLE register_history ADD COLUMN IF NOT EXISTS action TEXT;