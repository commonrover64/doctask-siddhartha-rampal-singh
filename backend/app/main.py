from fastapi import FastAPI
from app.db import get_pool
from app.schemas import LoanFileCreate, ReviewDecision
import hashlib
from fastapi import UploadFile
from app.graph.build import build_classify_graph
from app.graph.checkpointer import get_checkpointer
import uuid
from contextlib import asynccontextmanager
from app.operations import get_register, list_pending, list_facts, list_conflicts, decide_review_item

_classify_graph = None  # built during startup, not at module load, since it needs an await

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _classify_graph
    checkpointer = await get_checkpointer()
    _classify_graph = build_classify_graph(checkpointer)
    yield

app = FastAPI(title="Loan File Intelligence System", lifespan=lifespan)

@app.get("/health")
async def health():
    return {
        "status": "ok"
    }

@app.get("/db-health")
async def db_health():
    pool = await get_pool()
    async  with pool.acquire() as conn:
        result = await conn.fetchval("select 1")
    return {
        "db": "ok",
        "result": result,
    }

@app.post("/loan-files")
async def create_loan_file(payload: LoanFileCreate):
    # FastAPI has already validated `payload` against LoanFileCreate by
    # the time this function runs — if borrower_name were missing, the
    # request would've been rejected before reaching this line.
    pool = await get_pool()
    async with pool.acquire() as conn:
        loan_file_id = await conn.fetchval(
            "INSERT INTO loan_files (borrower_name) VALUES ($1) RETURNING loan_file_id",
            payload.borrower_name,
        )
        # $1 is a PLACEHOLDER, not string formatting — asyncpg sends the
        # query and the value separately to Postgres. This is what
        # prevents SQL injection; NEVER do f"...{payload.borrower_name}..."
        # to build a query string yourself.
        #
        # RETURNING loan_file_id asks Postgres to hand back the
        # auto-generated UUID from this exact insert, in the same
        # round-trip — otherwise you'd have no way to know which ID
        # Postgres just created for you.
    return {"loan_file_id": str(loan_file_id)}
    # str(...) because UUID objects aren't JSON-serializable by default —
    # FastAPI would error trying to return a raw UUID object.


@app.get("/loan-files")
async def list_loan_files():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT loan_file_id, borrower_name, created_at FROM loan_files ORDER BY created_at")
        # fetch() (not fetchval/fetchrow) = "give me back ALL matching rows"
    return [dict(r) for r in rows]
    # asyncpg returns special Record objects, not plain dicts — FastAPI
    # can't JSON-serialize those directly, so we convert each one to a
    # dict before returning.

@app.post("/loan-files/{loan_file_id}/documents")
async def upload_document(loan_file_id: str, file: UploadFile):
    # UploadFile is FastAPI's type for "this parameter comes from a
    # multipart file upload", not a JSON body. FastAPI automatically
    # renders a file-picker for this in /docs.

    content = await file.read()
    # .read() gives raw bytes. UploadFile is a stream under the hood
    # (so large files don't all sit in memory at once), so reading it
    # is itself an async operation.

    text = content.decode("utf-8", errors="ignore")
    # Our corpus docs are plain .txt, so utf-8 decode is enough for now.
    # errors="ignore" means: if a byte doesn't decode cleanly, skip it
    # rather than crashing, fine for now, we'll revisit for real PDFs.

    content_hash = hashlib.sha256(content).hexdigest()
    # Hash the RAW BYTES (not the decoded text) — this is the fingerprint
    # discussed above. hexdigest() turns the hash into a readable string.

    pool = await get_pool()
    async with pool.acquire() as conn:
        document_id = await conn.fetchval(
            """INSERT INTO documents (loan_file_id, file_path, raw_text, content_hash)
               VALUES ($1, $2, $3, $4)
               RETURNING document_id""",
            loan_file_id, file.filename, text, content_hash,
        )
    return {"document_id": str(document_id)}


@app.get("/loan-files/{loan_file_id}/documents")
async def list_documents(loan_file_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT document_id, file_path, doc_type, doc_type_confidence, received_at, needs_review FROM documents WHERE loan_file_id = $1 ORDER BY received_at",
            loan_file_id,
        )
    return [dict(r) for r in rows]

@app.post("/documents/{document_id}/process")
async def process_document(document_id: str):
    run_id = str(uuid.uuid4())  # generated before the graph even starts
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT raw_text, loan_file_id FROM documents WHERE document_id = $1", document_id
        )
        if row is None:
            return {"error": "document not found"}
        loan_file_id = row["loan_file_id"]

        await conn.execute(
            "INSERT INTO runs (run_id, document_id, loan_file_id) VALUES ($1, $2, $3)",
            run_id, document_id, loan_file_id,
        )  # written BEFORE the graph runs, this is what survives a crash
        print(f"run_id: {run_id}")  # your lifeline if the process dies before responding

        existing_facts = await _fetch_existing_facts(conn, loan_file_id)

        config = {"configurable": {"thread_id": run_id}}  # thread_id is how the checkpointer identifies this run
        result = await _classify_graph.ainvoke({
            "document_id": document_id, "loan_file_id": str(loan_file_id),
            "raw_text": row["raw_text"], "doc_type": "", "confidence": 0.0,
            "needs_review": False, "facts": [], "existing_facts": existing_facts, "conflicts": [],
        }, config=config)

        await _persist_pipeline_result(conn, document_id, loan_file_id, result, existing_facts)
        await conn.execute("UPDATE runs SET status = 'completed', finished_at = now() WHERE run_id = $1", run_id)

    return {
        "run_id": run_id, 
        **result
    }

@app.post("/runs/{run_id}/resume")
async def resume_run(run_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        run_row = await conn.fetchrow("SELECT * FROM runs WHERE run_id = $1", run_id)
        if run_row is None:
            return {"error": "run not found"}
        if run_row["status"] == "completed":
            return {"error": "run already completed, nothing to resume"}

        document_id, loan_file_id = run_row["document_id"], run_row["loan_file_id"]
        existing_facts = await _fetch_existing_facts(conn, loan_file_id)

        config = {"configurable": {"thread_id": run_id}}  # same thread_id, resumes instead of starting fresh
        result = await _classify_graph.ainvoke(None, config=config)  # None input = continue from last checkpoint

        await _persist_pipeline_result(conn, document_id, loan_file_id, result, existing_facts)
        await conn.execute("UPDATE runs SET status = 'completed', finished_at = now() WHERE run_id = $1", run_id)

    return {"run_id": run_id, **result}

async def _fetch_existing_facts(conn, loan_file_id):
    rows = await conn.fetch(
        """SELECT ef.fact_id, ef.field_name, ef.field_value
           FROM register r JOIN extracted_facts ef ON ef.fact_id = r.fact_id
           WHERE r.loan_file_id = $1""",
        loan_file_id,
    )
    return {r["field_name"]: {"fact_id": str(r["fact_id"]), "field_value": r["field_value"]} for r in rows}

async def _persist_pipeline_result(conn, document_id, loan_file_id, result, existing_facts):
    await conn.execute(
        "UPDATE documents SET doc_type = $1, doc_type_confidence = $2, needs_review = $3 WHERE document_id = $4",
        result["doc_type"], result["confidence"], result["needs_review"], document_id,
    )
    conflicts_by_field = {c["field_name"]: c for c in result["conflicts"]}  # lookup by field for the loop below

    for field in result["facts"]:
        field_name = field.get("field_name")
        fact_id = await conn.fetchval(
            """INSERT INTO extracted_facts (document_id, loan_file_id, field_name, field_value, quote)
               VALUES ($1, $2, $3, $4, $5) RETURNING fact_id""",
            document_id, loan_file_id, field_name, field.get("field_value"), field.get("quote"),
        )
        conflict = conflicts_by_field.get(field_name)
        if conflict:
            conflict_id = await conn.fetchval(
                """INSERT INTO conflicts (loan_file_id, field_name, fact_id_old, fact_id_new)
                   VALUES ($1, $2, $3, $4) RETURNING conflict_id""",
                loan_file_id, field_name, conflict["fact_id_old"], fact_id,
            )
            await conn.execute(
                """INSERT INTO review_queue (loan_file_id, item_type, ref_id, field_name)
                   VALUES ($1, 'conflict', $2, $3)""",
                loan_file_id, conflict_id, field_name,
            )
        elif field_name not in existing_facts:  # brand new field, needs approval before first entry
            await conn.execute(
                """INSERT INTO review_queue (loan_file_id, item_type, ref_id, field_name)
                   VALUES ($1, 'register_update', $2, $3)""",
                loan_file_id, fact_id, field_name,
            )

@app.get("/loan-files/{loan_file_id}/facts")
async def facts_endpoint(loan_file_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await list_facts(conn, loan_file_id)

@app.get("/loan-files/{loan_file_id}/conflicts")
async def conflicts_endpoint(loan_file_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await list_conflicts(conn, loan_file_id)

@app.get("/review/{loan_file_id}/pending")
async def pending_endpoint(loan_file_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await list_pending(conn, loan_file_id)

@app.post("/review/{item_id}/decide")
async def decide_endpoint(item_id: str, decision: ReviewDecision):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await decide_review_item(conn, item_id, decision)
    
@app.get("/loan-files/{loan_file_id}/register")
async def register_endpoint(loan_file_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await get_register(conn, loan_file_id)