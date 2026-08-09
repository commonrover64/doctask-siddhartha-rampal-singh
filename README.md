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

## What's not built yet

- Extraction (pulling structured facts out of documents, with citations)
- Reconciliation (detecting when two documents disagree on a field)
- The human review queue and approval endpoint
- Rule/playbook checking (movement 2)
- Incremental updates on new document arrival (movement 3)
- Resumability (LangGraph checkpointing)
- MCP server
- Automated tests
- Frontend

## Key decisions made while building

- **Groq instead of Anthropic for the LLM calls.** Free tier, no card
  required, sufficient for structured extraction/classification tasks.
  The assignment doesn't mandate a specific model provider.
- **Migrations are versioned `.sql` files in `db/migrations/`, applied by
  a Python runner (`app/migrate.py`)** A `schema_migrations` table tracks what's already applied so
  the runner is safe to re-run. Every migration uses
  `CREATE TABLE IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` for safety.
- **Confidence-based routing in the classification graph uses a threshold
  of 0.85, not the more intuitive-sounding 0.5.** Testing showed Llama
  3.3's self-reported confidence is poorly calibrated: even genuinely
  ambiguous, non-loan-related text (e.g. unrelated call notes) scored
  0.8 confidence. Self-reported LLM confidence is a heuristic, not a
  calibrated probability. A production system would want log-probabilities,
  an ensemble, or a dedicated calibration step; out of scope here.
- **Schema columns are added when the phase that populates them is
  built, not all up front.** `doc_type` and `doc_type_confidence` were
  added to `documents` slightly ahead of the classification node (a
  deliberate small exception) so the column and the code that fills it
  could be reviewed together. `embedding vector(...)` is deferred
  entirely until an embedding model is chosen, to avoid hardcoding a
  vector dimension before it's needed.

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