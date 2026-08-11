CREATE TABLE IF NOT EXISTS runs (
    run_id        UUID PRIMARY KEY,
    document_id   UUID NOT NULL REFERENCES documents(document_id),
    loan_file_id  UUID NOT NULL REFERENCES loan_files(loan_file_id),
    status        TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ
);