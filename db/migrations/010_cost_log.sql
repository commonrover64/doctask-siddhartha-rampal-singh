-- one row per LLM call, tagged with which run and which stage it belonged
-- to, this is what makes "stage by stage" cost reporting possible
CREATE TABLE IF NOT EXISTS cost_log (
    log_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id       UUID NOT NULL REFERENCES runs(run_id),
    stage        TEXT NOT NULL,
    tokens_in    INTEGER NOT NULL DEFAULT 0,
    tokens_out   INTEGER NOT NULL DEFAULT 0,
    latency_ms   INTEGER NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);