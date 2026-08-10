from fastapi import FastAPI
from app.db import get_pool
from app.models.schemas import LoanFileCreate
import hashlib
from fastapi import UploadFile
from app.graph.build import build_classify_graph
from app.schemas import ReviewDecision

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
            "SELECT document_id, file_path, doc_type, doc_type_confidence, received_at, needs_review FROM documents WHERE loan_file_id = $1 ORDER BY received_at",
            loan_file_id,
        )
    return [dict(r) for r in rows]

_classify_graph = build_classify_graph()

@app.post("/documents/{document_id}/process")
async def process_document(document_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT raw_text, loan_file_id FROM documents WHERE document_id = $1", document_id)
        if row is None:
            return {
                "error": "document not found"
            }
        loan_file_id = row["loan_file_id"]

        # fetch the MOST RECENT fact per field_name for this loan file,
        # this is what reconcile_facts compares against
        existing_rows = await conn.fetch(
            """SELECT ef.fact_id, ef.field_name, ef.field_value
            FROM register r
            JOIN extracted_facts ef ON ef.fact_id = r.fact_id
            WHERE r.loan_file_id = $1""", 
            loan_file_id,
        )

        existing_facts = {
            r["field_name"]: {
                "fact_id": str(r["fact_id"]),
                "field_value": r["field_value"],
            }
            for r in existing_rows
        }  
        
        result = await _classify_graph.ainvoke({
            "document_id": document_id,
            "loan_file_id": str(row["loan_file_id"]),
            "raw_text": row["raw_text"],
            "doc_type": "",
            "confidence": 0.0,
            "needs_review": False,  # default, only flag_for_review flips this
            "facts": [],
            "existing_facts": existing_facts,
            "conflicts": [], 
        })
        # .ainvoke() runs the graph start to finish and returns the final
        # state — result["doc_type"] and result["confidence"] are now
        # whatever classify_doc set them to.

        await conn.execute(
            "UPDATE documents SET doc_type = $1, doc_type_confidence = $2, needs_review = $3 WHERE document_id = $4",
            result["doc_type"], result["confidence"], result["needs_review"], document_id,
        )

        # build a lookup from field_name -> conflict, so once we know the
        # new fact_id (after inserting it below) we can fill in fact_id_new
        conflicts_by_field = {
            c["field_name"]: c for c in result["conflicts"]
        }

        for field in result["facts"]:
            # Insert this newly extracted fact as its own row, RETURNING fact_id
            # gives us back the UUID Postgres just generated for it, we need this
            # ID below to link a conflict to the fact that caused it.
            fact_id = await conn.fetchval(
                """INSERT INTO extracted_facts (document_id, loan_file_id, field_name, field_value, quote)
                VALUES ($1, $2, $3, $4, $5) RETURNING fact_id""",
                document_id, loan_file_id, field.get("field_name"), field.get("field_value"), field.get("quote"),
            )
            field_name = field.get("field_name")

            # reconcile_facts (inside the graph) already decided WHICH fields
            # conflict, but it ran before this fact existed in the database, so
            # it couldn't know this fact's fact_id yet. Look up by field_name to
            # find the conflict this specific fact belongs to, if any.
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
            else:
                prior = existing_facts.get(field_name)
                if prior is None:
                    # brand new field, nothing in the register yet, needs approval to create the first entry
                    await conn.execute(
                        """INSERT INTO review_queue (loan_file_id, item_type, ref_id, field_name)
                        VALUES ($1, 'register_update', $2, $3)""",
                        loan_file_id, fact_id, field_name,
                    )
                # else: prior exists and matches (no conflict was raised), nothing
                # changed, nothing to review, this is what makes an update cost
                # like an update instead of a full re-review every time
    return {
        "document_id": document_id,
        "doc_type": result["doc_type"],
        "confidence": result["confidence"],
        "needs_review": result["needs_review"],
        "facts": result["facts"],
        "conflicts": result["conflicts"],
    }

@app.get("/loan-files/{loan_file_id}/facts")
async def list_facts(loan_file_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT field_name, field_value, quote, document_id FROM extracted_facts WHERE loan_file_id = $1 ORDER BY extracted_at",
            loan_file_id,
        )
    return [dict(r) for r in rows]

@app.get("/loan-files/{loan_file_id}/conflicts")
async def list_conflicts(loan_file_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT * FROM conflicts WHERE loan_file_id = $1 ORDER BY opened_at""",
            loan_file_id,
        )
    return [dict(r) for r in rows]

@app.get("/review/{loan_file_id}/pending")
async def list_pending(loan_file_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT * FROM review_queue WHERE loan_file_id = $1 AND status = 'pending' ORDER BY created_at""",
            loan_file_id,
        )
    return [dict(r) for r in rows]

@app.post("/review/{item_id}/decide")
async def decide_review_item(item_id: str, decision: ReviewDecision):
    pool = await get_pool()
    async with pool.acquire() as conn:
        # everything inside this transaction either all commits or all
        # rolls back together, and the FOR UPDATE lock below stays held
        # for the whole block, not just the one SELECT
        async with conn.transaction():
            item = await conn.fetchrow(
                "SELECT * FROM review_queue WHERE item_id = $1 FOR UPDATE",
                item_id,
            )

            if item is None:
                return {"error": "review item not found"}
            if item["status"] != "pending":
                # someone already decided this item, don't apply a second
                # decision on top of it
                return {"error": f"item already {item['status']}"}

            if decision.decision == "reject":
                await conn.execute(
                    "UPDATE review_queue SET status = 'rejected', decided_at = now() WHERE item_id = $1",
                    item_id,
                )
                return {"item_id": item_id, "status": "rejected"}

            # approve path: figure out which fact_id actually wins
            if item["item_type"] == "register_update":
                # no conflict involved, only one fact to choose from
                chosen_fact_id = item["ref_id"]
            else:  # item_type == "conflict"
                conflict = await conn.fetchrow(
                    "SELECT * FROM conflicts WHERE conflict_id = $1",
                    item["ref_id"],
                )
                # reviewer picks which side of the conflict wins, defaults
                # to the newer value if they didn't specify
                keep = decision.keep or "new"
                chosen_fact_id = conflict["fact_id_new"] if keep == "new" else conflict["fact_id_old"]
                await conn.execute(
                    "UPDATE conflicts SET status = 'resolved' WHERE conflict_id = $1",
                    item["ref_id"],
                )

            # whatever was in the register before, for the audit trail below
            old = await conn.fetchrow(
                "SELECT fact_id FROM register WHERE loan_file_id = $1 AND field_name = $2",
                item["loan_file_id"], item["field_name"],
            )

            # ON CONFLICT DO UPDATE: first approval for this field inserts
            # a fresh row, any later approval just overwrites it, register
            # only ever holds the CURRENT accepted value
            await conn.execute(
                """INSERT INTO register (loan_file_id, field_name, fact_id, updated_at)
                   VALUES ($1, $2, $3, now())
                   ON CONFLICT (loan_file_id, field_name) DO UPDATE SET fact_id = $3, updated_at = now()""",
                item["loan_file_id"], item["field_name"], chosen_fact_id,
            )

            # append-only, this row is never touched again, it's what lets
            # you answer "what changed, when, from what" without guessing
            await conn.execute(
                """INSERT INTO register_history (loan_file_id, field_name, old_fact_id, new_fact_id)
                   VALUES ($1, $2, $3, $4)""",
                item["loan_file_id"], item["field_name"],
                old["fact_id"] if old else None, chosen_fact_id,
            )

            await conn.execute(
                "UPDATE review_queue SET status = 'approved', decided_at = now() WHERE item_id = $1",
                item_id,
            )

    return {
        "item_id": item_id, 
        "status": "approved"
    }

@app.get("/loan-files/{loan_file_id}/register")
async def get_register(loan_file_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT r.field_name, ef.field_value, ef.quote, r.updated_at
               FROM register r JOIN extracted_facts ef ON ef.fact_id = r.fact_id
               WHERE r.loan_file_id = $1 ORDER BY r.field_name""",
            loan_file_id,
        )
    return [dict(r) for r in rows]