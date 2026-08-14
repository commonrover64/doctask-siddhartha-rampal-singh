# Loan File Intelligence System

An agentic system that owns a loan file end to end: understands a pile of
mixed-format documents, checks it against an underwriting playbook, and
stays current as new documents arrive, with a human gate on every commit
and an MCP interface so a machine can drive the whole flow.

This README is written incrementally as the project is built, not all at
once at the end. Sections marked "not yet built" are genuinely not built
yet, not placeholders.

## Setup

Requires Python 3.12+, a Neon Postgres account (free tier works, pgvector
supported natively), and a free Groq API key (console.groq.com, no card / payment
required).

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# fill in DATABASE_URL (from Neon) and GROQ_API_KEY (from console.groq.com)

python -m app.migrate   # applies db/migrations/*.sql in order
uvicorn app.main:app --reload
```

Then open `http://127.0.0.1:8000/docs` for the interactive Swagger API.

## What's built so far

- FastAPI app with health check and Neon Postgres connection pooling

- `loan_files` and `documents` tables, via versioned migrations in
  `db/migrations/` (applied with `app/migrate.py`, not by hand in a web
  editor)

- Document upload endpoint with content-hash based dedup (`UNIQUE`
  constraint on `loan_file_id, content_hash`)

- A LangGraph classification graph (`app/graph/`): one node calls Groq
  to classify a document's type, a conditional edge routes low-confidence
  results to a `flag_for_review` node instead of accepting a guess
  silently

  - Extraction (`app/graph/nodes.py::extract_facts`): pulls structured
  facts (loan_amount, income, dti_ratio, etc) from documents into an
  append-only `extracted_facts` table, each fact stores the exact quote
  it was extracted from as a citation

- Reconciliation (`app/graph/nodes.py::reconcile_facts`): compares a
  newly extracted fact against the most recent fact on record for the
  same field, opens a row in `conflicts` if they disagree beyond
  tolerance instead of silently picking one. Numbers get a tolerance
  for formatting differences, everything else needs an exact match

- Human review queue and register: `register` holds only approved
  facts, `review_queue` holds pending decisions, `POST
  /review/{item_id}/decide` is the single approval gate, rejecting one
  item is its own transaction and never touches siblings,
  `register_history` is an append-only audit trail

- **Resumability uses LangGraph's built-in Postgres checkpointer**
  rather than custom save/resume logic. thread_id = run_id, a `runs`
  table records the run_id before the graph starts so it survives a
  crash even if the process dies before responding to the request.

- **MCP server** (`app/mcp_server.py`) exposes register/facts/conflicts
  reads and the review-decision gate as tools, both REST and MCP call
  into the same `app/operations.py` functions, so a human via `/docs`
  and a program via MCP get identical behavior with no duplicated logic.
  Known gap: `process_document` and `resume_run` remain REST-only for
  now, since they depend on the compiled graph object built in main.py's
  startup event, moving them into operations.py would need a shared
  app-state pattern that felt like unnecessary complexity. 

- rule/playbook checking: `app/rules.py` runs a
  user-supplied playbook (`app/playbook.yaml`) against a loan file,
  one findings row per rule per stage (completeness, accuracy,
  consistency, regulatory), always written even when clean, so "no
  findings" is a real queryable result. Four rules implemented:
  required doc types present, loan amount consistency after
  amendments, embedded-instruction scanning, appraisal recency window.

- watched directory: `app/watcher.py` watches
  `watched_incoming/<loan_file_id>/`, on a new `.txt` file, ingests it
  with the same content-hash dedup as the upload endpoint and runs
  the pipeline on just that one document, not the whole loan file.
  Shares `process_document_op` with the REST `/process` endpoint via
  `app/operations.py`, so both entry points behave identically.

- Automated tests (`tests/`): no live LLM key required, `app/llm.py`
  has a test-only override hook. Covers embedded-instruction detection
  (fake LLM that would comply if asked, proving safety comes from the
  rule not the model), concurrent-run serialization on the same loan
  file vs parallel execution on different ones, and resumability via
  LangGraph's `interrupt_after`.

## What's not built yet

- Frontend

## Key decisions made while building

- **Groq instead of Anthropic for the LLM calls.** Free tier, no card
  required, sufficient for structured extraction/classification tasks.

- **Migrations are versioned `.sql` files in `db/migrations/`, applied by
  a Python runner (`app/migrate.py`)** A `schema_migrations` table tracks what's already applied so
  the runner is safe to re-run. Every migration uses
  `CREATE TABLE IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` for safety.

- **Confidence-based routing in the classification graph uses a threshold
  of 0.85, not the more intuitive-sounding 0.5.** Testing showed Llama
  3.3's self-reported confidence is poorly calibrated: even genuinely
  ambiguous, non-loan-related text (e.g. unrelated call notes) scored
  0.8 confidence. Self-reported LLM confidence is a heuristic, not a
  calibrated probability.

- **Schema columns are added when the phase that populates them is
  built, not all up front.** `doc_type` and `doc_type_confidence` were
  added to `documents` slightly ahead of the classification node (a
  deliberate small exception) so the column and the code that fills it
  could be reviewed together.

- **Reconciliation originally only compared new facts against the
  approved register, not against other pending review items.**
  Building the watcher and feeding it several documents for the same
  loan file surfaced this: multiple documents mentioning the same
  unapproved field each spawned their own `register_update` item
  instead of joining the one already waiting. Fixed by having
  `_fetch_existing_facts` also check pending `register_update` items,
  and by superseding a pending item into a real conflict if a later
  document disagrees with it before a human ever saw it.
  `extracted_facts` stayed intentionally append-only throughout, the
  fix was entirely in what counts as "the current candidate value" for
  reconciliation, not in the fact history itself.
  This fix alone wasn't sufficient though, testing with a full folder of documents
  dropped at once still produced duplicates, because two runs could
  both read the same "nothing pending yet" state before either had
  written its result. That was a concurrency gap, not a
  reconciliation gap, and needed the locking mechanism fix below to fully close.

- **Concurrency serialization uses `pg_advisory_xact_lock` (transaction-
  scoped), not the plain session-scoped `pg_advisory_lock`.** The
  session version only releases on an explicit unlock call, so a run
  that fails partway through would leave the lock held forever,
  hanging every future run on that loan file. The transaction-scoped
  version (`pg_advisory_xact_lock`) releases automatically on commit or rollback, no leak is
  possible. Lock key computed via Postgres's `hashtextextended`
  rather than Python's `hash()`, which is randomized per process and
  would let the watcher and API server compute different keys for the
  same loan file.

- **Writing the injection test caught a real bug**: the playbook rule
  referenced `no_embedded_instructions`, `CHECK_FUNCTIONS` was keyed
  `no_embedding_instructions`. The mismatch meant the embedded-
  instruction rule silently returned `inconclusive` every time instead
  of ever running, no error, no crash, just quietly not checking
  anything. Would not have been caught by manual testing alone.

## Repo layout

```
backend/app/
  main.py           FastAPI app and all routes
  db.py             Neon connection pool
  migrate.py        Migration runner
  llm.py            Groq API client
  graph/
    state.py        LangGraph state definition
    nodes.py         Node functions
    build.py          Graph assembly and routing
db/migrations/       Versioned schema changes, applied via app/migrate.py
```