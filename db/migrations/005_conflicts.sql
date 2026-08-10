CREATE TABLE IF NOT EXISTS conflicts (
    conflict_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_file_id  UUID NOT NULL REFERENCES loan_files(loan_file_id),
    field_name    TEXT NOT NULL,
    fact_id_old   UUID NOT NULL REFERENCES extracted_facts(fact_id),
    fact_id_new   UUID NOT NULL REFERENCES extracted_facts(fact_id),
    status        TEXT NOT NULL DEFAULT 'open',
    opened_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);