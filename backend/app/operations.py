"""Shared logic, called by both the REST routes in main.py and the MCP
tools in mcp_server.py. Neither one contains real logic itself, they're
both thin wrappers around these functions, so a human using /docs and a
program using MCP always get identical behavior."""

from app.rules import run_playbook
import uuid
from langgraph.errors import EmptyInputError
from app.db import loan_file_lock

_graph_ref = {} # holds the compiled graph, set once from main.py startup

def set_graph(graph):
    _graph_ref["graph"] = graph

async def process_document_op(pool, document_id: str):
    run_id = str(uuid.uuid4())
    async with pool.acquire() as lookup_conn:  # quick lookup before we know which lock to take
        row = await lookup_conn.fetchrow(
            "SELECT raw_text, loan_file_id FROM documents WHERE document_id = $1", 
            document_id
        )
    if row is None:
        return {
            "error": "document not found"
        }
    loan_file_id = row["loan_file_id"]

    async with loan_file_lock(str(loan_file_id)) as conn:   # serializes against other runs on THIS loan file only
        await conn.execute(
            "INSERT INTO runs (run_id, document_id, loan_file_id) VALUES ($1, $2, $3)",
            run_id, document_id, loan_file_id,
        )  # written BEFORE the graph runs, this is what survives a crash
        print(f"run_id: {run_id}")  # your lifeline if the process dies before responding

        existing_facts = await _fetch_existing_facts(conn, loan_file_id)

        config = {"configurable": {"thread_id": run_id}}  # thread_id is how the checkpointer identifies this run
        result = await _graph_ref["graph"].ainvoke({
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

async def resume_run_op(pool, run_id: str):
    async with pool.acquire() as lookup_conn:
        run_row = await lookup_conn.fetchrow("SELECT * FROM runs WHERE run_id = $1", run_id)
        if run_row is None:
            return {"error": "run not found"}
        if run_row["status"] == "completed":
            return {"error": "run already completed, nothing to resume"}

        document_id, loan_file_id = run_row["document_id"], run_row["loan_file_id"]

        async with loan_file_lock(str(loan_file_id)) as conn:
            existing_facts = await _fetch_existing_facts(conn, loan_file_id)

            config = {"configurable": {"thread_id": run_id}}  # same thread_id, resumes instead of starting fresh

            try:
                result = await _graph_ref["graph"].ainvoke(None, config=config) # None input = continue from last checkpoint
            except EmptyInputError:
                return {
                    "error": "no checkpoint found for this run_id",
                }

            await _persist_pipeline_result(conn, document_id, loan_file_id, result, existing_facts)
            await conn.execute("UPDATE runs SET status = 'completed', finished_at = now() WHERE run_id = $1", run_id)
            
    return {"run_id": run_id, **result}

async def _fetch_existing_facts(conn, loan_file_id):
    rows = await conn.fetch(
        """SELECT r.field_name, ef.fact_id, ef.field_value
           FROM register r JOIN extracted_facts ef ON ef.fact_id = r.fact_id
           WHERE r.loan_file_id = $1""",
        loan_file_id,
    )
    existing = {
        r["field_name"]: {"fact_id": str(r["fact_id"]), "field_value": r["field_value"], "pending_item_id": None}
        for r in rows
    }  # approved values, these always win over pending ones below

    pending_rows = await conn.fetch(
        """SELECT rq.item_id, rq.field_name, ef.fact_id, ef.field_value
           FROM review_queue rq JOIN extracted_facts ef ON ef.fact_id = rq.ref_id
           WHERE rq.loan_file_id = $1 AND rq.item_type = 'register_update' AND rq.status = 'pending'
           ORDER BY rq.created_at DESC""",
        loan_file_id,
    )
    for r in pending_rows:
        if r["field_name"] not in existing:  # don't override an approved value with a pending one
            existing[r["field_name"]] = {
                "fact_id": str(r["fact_id"]), "field_value": r["field_value"],
                "pending_item_id": str(r["item_id"]),  # lets the caller supersede this if it turns into a conflict
            }
    return existing

async def _persist_pipeline_result(conn, document_id, loan_file_id, result, existing_facts):
    await conn.execute(
        "UPDATE documents SET doc_type = $1, doc_type_confidence = $2, needs_review = $3 WHERE document_id = $4",
        result["doc_type"], result["confidence"], result["needs_review"], document_id,
    )
    conflicts_by_field = {c["field_name"]: c for c in result["conflicts"]}

    fields_with_open_conflict = {
        r["field_name"] for r in await conn.fetch(
            """SELECT field_name FROM review_queue
               WHERE loan_file_id = $1 AND item_type = 'conflict' AND status = 'pending'""",
            loan_file_id,
        )
    }  # already disputed, dont pile on more review items for these

    for field in result["facts"]:
        field_name = field.get("field_name")
        fact_id = await conn.fetchval(
            """INSERT INTO extracted_facts (document_id, loan_file_id, field_name, field_value, quote)
               VALUES ($1, $2, $3, $4, $5) RETURNING fact_id""",
            document_id, loan_file_id, field_name, field.get("field_value"), field.get("quote"),
        )  # always recorded, append-only, regardless of what happens below

        if field_name in fields_with_open_conflict:
            continue  # fact recorded, but no new review item, human already has this field queued

        conflict = conflicts_by_field.get(field_name)
        prior = existing_facts.get(field_name)

        if conflict:
            conflict_id = await conn.fetchval(
                """INSERT INTO conflicts (loan_file_id, field_name, fact_id_old, fact_id_new)
                   VALUES ($1, $2, $3, $4) RETURNING conflict_id""",
                loan_file_id, field_name, conflict["fact_id_old"], fact_id,
            )
            if prior and prior.get("pending_item_id"):
                await conn.execute(
                    "UPDATE review_queue SET status = 'superseded', decided_at = now() WHERE item_id = $1",
                    prior["pending_item_id"],
                )  # old pending item folded into this conflict, no longer stands alone
            await conn.execute(
                """INSERT INTO review_queue (loan_file_id, item_type, ref_id, field_name)
                   VALUES ($1, 'conflict', $2, $3)""",
                loan_file_id, conflict_id, field_name,
            )
        elif prior is None:
            await conn.execute(
                """INSERT INTO review_queue (loan_file_id, item_type, ref_id, field_name)
                   VALUES ($1, 'register_update', $2, $3)""",
                loan_file_id, fact_id, field_name,
            )  # brand new field, nothing pending or approved yet
        # else: prior exists (approved or pending) and agrees, no new item, this is the actual fix
    
async def get_register(conn, loan_file_id: str):
    rows = await conn.fetch(
        """SELECT r.field_name, ef.field_value, ef.quote, r.updated_at
        FROM register r JOIN extracted_facts ef ON ef.fact_id = r.fact_id
        WHERE r.loan_file_id = $1 ORDER BY r.field_name""",
        loan_file_id,
    )
    return [dict(r) for r in rows]

async def list_pending(conn, loan_file_id: str):
    rows = await conn.fetch(
        "SELECT * FROM review_queue WHERE loan_file_id = $1 AND status = 'pending' ORDER BY created_at",
        loan_file_id,
    )
    return [dict(r) for r in rows]

async def list_facts(conn, loan_file_id: str):
    rows = await conn.fetch(
        "SELECT field_name, field_value, quote, document_id FROM extracted_facts WHERE loan_file_id = $1 ORDER BY extracted_at",
        loan_file_id,
    )
    return [dict(r) for r in rows]

async def list_conflicts(conn, loan_file_id: str):
    rows = await conn.fetch(
        "SELECT * FROM conflicts WHERE loan_file_id = $1 ORDER BY opened_at", loan_file_id,
    )
    return [dict(r) for r in rows]

async def decide_review_item(conn, item_id: str, decision):
    # decision has .decision ("approve"/"reject") and .keep ("old"/"new"/None)
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
            # someone already decided this item, don't apply a second decision on top of it
            return {"error": f"item already {item['status']}"}

        if decision.decision == "reject":
            await conn.execute(
                "UPDATE review_queue SET status = 'rejected', decided_at = now() WHERE item_id = $1",
                item_id,
            )
            return {
                "item_id": item_id, 
                "status": "rejected"
            }

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

async def check_loan_file(conn, loan_file_id: str):
    return await run_playbook(conn, loan_file_id)

async def list_findings(conn, loan_file_id: str):
    rows = await conn.fetch(
        "SELECT * FROM findings WHERE loan_file_id = $1 ORDER BY created_at DESC",
        loan_file_id
    ) 
    return [dict(r) for r in rows]
