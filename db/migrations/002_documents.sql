CREATE TABLE IF NOT EXISTS documents (
    document_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_file_id         UUID NOT NULL REFERENCES loan_files(loan_file_id),
    file_path            TEXT NOT NULL,
    doc_type             TEXT,      -- null until classify_doc runs (Phase 5)
    doc_type_confidence  REAL,      -- null until classify_doc runs (Phase 5)
    raw_text             TEXT,      -- extracted plain text, used for spans
    content_hash         TEXT NOT NULL,   -- sha256, used for dedup on re-upload
    received_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (loan_file_id, content_hash)
);