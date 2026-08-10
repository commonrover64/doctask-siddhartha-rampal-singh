-- register holds only APPROVED facts, one row per loan_file_id + field_name.

CREATE TABLE IF NOT EXISTS register (
    loan_file_id  UUID NOT NULL REFERENCES loan_files(loan_file_id),
    field_name    TEXT NOT NULL,
    fact_id       UUID NOT NULL REFERENCES extracted_facts(fact_id),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (loan_file_id, field_name)
);

-- append-only audit trail, answers "what changed, when, from what to what"
CREATE TABLE IF NOT EXISTS register_history (
    history_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_file_id  UUID NOT NULL REFERENCES loan_files(loan_file_id),
    field_name    TEXT NOT NULL,
    old_fact_id   UUID REFERENCES extracted_facts(fact_id),
    new_fact_id   UUID NOT NULL REFERENCES extracted_facts(fact_id),
    changed_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS review_queue (
    item_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_file_id  UUID NOT NULL REFERENCES loan_files(loan_file_id),
    item_type     TEXT NOT NULL CHECK (item_type IN ('register_update', 'conflict')),
    ref_id        UUID NOT NULL,   -- fact_id if register_update, conflict_id if conflict
    field_name    TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at    TIMESTAMPTZ
);