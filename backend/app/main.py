from fastapi import FastAPI
from app.db import get_pool
from app.models.schemas import LoanFileCreate
import hashlib
from fastapi import UploadFile
from app.graph.build import build_classify_graph

app = FastAPI(title="Loan File Intelligence System")

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
            "SELECT document_id, file_path, doc_type, doc_type_confidence, received_at FROM documents WHERE loan_file_id = $1 ORDER BY received_at",
            loan_file_id,
        )
    return [dict(r) for r in rows]

_classify_graph = build_classify_graph()

@app.post("/documents/{document_id}/classify")
async def classify_document(document_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT raw_text FROM documents WHERE document_id = $1", document_id)
        if row is None:
            return {
                "error": "document not found"
            }
        result = await _classify_graph.ainvoke({
            "document_id": document_id,
            "raw_text": row["raw_text"],
            "doc_type": "",
            "confidence": 0.0,
        })
        # .ainvoke() runs the graph start to finish and returns the final
        # state — result["doc_type"] and result["confidence"] are now
        # whatever classify_doc set them to.

        await conn.execute(
            "UPDATE documents SET doc_type = $1, doc_type_confidence = $2 WHERE document_id = $3",
            result["doc_type"], result["confidence"], document_id,
        )
    return {
        "document_id": document_id,
        "doc_type": result["doc_type"],
        "confidence": result["confidence"],
    }