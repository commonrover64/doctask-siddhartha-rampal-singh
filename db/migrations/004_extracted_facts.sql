CREATE TABLE IF NOT EXISTS extracted_facts (
    fact_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID NOT NULL REFERENCES documents(document_id),
    loan_file_id  UUID NOT NULL REFERENCES loan_files(loan_file_id),
    field_name    TEXT NOT NULL,
    field_value   TEXT NOT NULL,
    quote         TEXT,     -- the exact source phrase this value came from
    extracted_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);