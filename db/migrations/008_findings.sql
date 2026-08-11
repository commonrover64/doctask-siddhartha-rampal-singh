CREATE TABLE IF NOT EXISTS findings (
    finding_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_file_id  UUID NOT NULL REFERENCES loan_files(loan_file_id),
    stage         TEXT NOT NULL,
    rule_id       TEXT NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('clean', 'violation', 'inconclusive')),
    detail        TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);