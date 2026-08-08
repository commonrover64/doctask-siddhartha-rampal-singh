-- pgcrypto gives us gen_random_uuid() — lets Postgres generate the ID
-- itself instead of us generating one in Python and hoping it's unique.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE loan_files (
    loan_file_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- DEFAULT gen_random_uuid() means: if we don't provide an ID on
    -- INSERT, Postgres makes one for us automatically.

    borrower_name TEXT NOT NULL,
    -- NOT NULL means Postgres will reject any insert missing this —
    -- a safety net so bad data can't sneak in even if our Python code
    -- has a bug.

    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
    -- TIMESTAMPTZ (not plain TIMESTAMP) stores timezone-aware time.
    -- Always use TIMESTAMPTZ for anything you'll compare/sort later —
    -- plain TIMESTAMP causes real bugs once servers cross timezones.
);