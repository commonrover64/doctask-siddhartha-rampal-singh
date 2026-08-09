CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS loan_files (
    loan_file_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    borrower_name TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);