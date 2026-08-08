from fastapi import FastAPI
from app.db import get_pool
from app.models.schemas import LoanFileCreate

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