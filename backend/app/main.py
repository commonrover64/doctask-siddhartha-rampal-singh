from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db import get_pool
from app.schemas import LoanFileCreate, ReviewDecision
import hashlib
from fastapi import UploadFile
from app.graph.build import build_classify_graph
from app.graph.checkpointer import get_checkpointer
from contextlib import asynccontextmanager
from app.operations import (get_register, list_pending, list_facts, list_conflicts, 
        decide_review_item, check_loan_file, list_findings, 
        process_document_op, set_graph, resume_run_op, list_changelog, 
        get_cost_report, get_loan_file_cost_report, delete_loan_file
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    checkpointer = await get_checkpointer()
    graph = build_classify_graph(checkpointer)

    # for drawing the graph  
    # graph_png = graph.get_graph().draw_mermaid_png()
    # with open ("graph_layout.png", "wb") as f:
    #     f.write(graph_png)``

    set_graph(graph) # hands the graph to operations.py, replaces the old global _classify_graph
    yield

app = FastAPI(title="Loan File Intelligence System", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite's default dev server port
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_UPLOAD_BYTES = 2 * 1024 * 1024 # 2mb enough for plain text loan documents

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

    if not file.filename.lower().endswith(".txt"):
        return {
            "error": "only .txt files are accepted"
        }

    # UploadFile is FastAPI's type for "this parameter comes from a
    # multipart file upload", not a JSON body. FastAPI automatically
    # renders a file-picker for this in /docs.

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        return {
            "error": f"file too large, max {MAX_UPLOAD_BYTES} bytes"
        }
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
               ON CONFLICT (loan_file_id, content_hash) DO NOTHING
               RETURNING document_id""",
            loan_file_id, file.filename, text, content_hash,
        )
        if document_id is None:
            # same content already on file, tell the caller which document it already is and whether it's been processed
            existing = await conn.fetchrow(
                "SELECT document_id, doc_type FROM documents WHERE loan_file_id = $1 AND content_hash = $2",
                loan_file_id, content_hash,
            )
            return {
                "documenmt_id": str(existing["document_id"]),
                "duplicate": True,
                "already_processed": existing["doc_type"] is not None,
            }

    return {
        "document_id": str(document_id),
        "duplicate": False,
        "already_processed": False,
    }


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
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await process_document_op(pool, document_id)

@app.post("/runs/{run_id}/resume")
async def resume_run(run_id: str):
    pool = await get_pool()
    return await resume_run_op(pool, run_id)
    
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

@app.post("/loan-files/{loan_file_id}/check")
async def check_endpoint(loan_file_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await check_loan_file(conn, loan_file_id)

@app.get("/loan-files/{loan_file_id}/findings")
async def findings_endpoint(loan_file_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await list_findings(conn, loan_file_id)


@app.get("/loan-files/{loan_file_id}/changelog")
async def changelog_endpoint(loan_file_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await list_changelog(conn, loan_file_id)

    
@app.get("/runs/{run_id}/cost")
async def cost_endpoint(run_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await get_cost_report(conn, run_id)


@app.get("/loan-files/{loan_file_id}/cost")
async def loan_file_cost_endpoint(loan_file_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await get_loan_file_cost_report(conn, loan_file_id)

@app.delete("/loan-files/{loan_file_id}")
async def delete_loan_file_endpoint(loan_file_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await delete_loan_file(conn, loan_file_id)