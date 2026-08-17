"""Shared logic, called by both the REST routes in main.py and the MCP
tools in mcp_server.py. Neither one contains real logic itself, they're
both thin wrappers around these functions, so a human using /docs and a
program using MCP always get identical behavior."""

from app.rules import run_playbook
import uuid
from langgraph.errors import EmptyInputError
from app.db import loan_file_lock
from app.llm import drain_usage_log

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
        await _persist_cost_log(conn, run_id)
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
            await _persist_cost_log(conn, run_id)
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
    items = []
    for r in rows:
        item = dict(r)
        if item["item_type"] == "register_update":
            fact = await conn.fetchrow(
                "SELECT field_value, quote FROM extracted_facts WHERE fact_id = $1", item["ref_id"]
            )
            item["old_value"] = None  # nothing existed before this
            item["new_value"] = fact["field_value"] if fact else None
            item["new_quote"] = fact["quote"] if fact else None
        else:  # conflict
            conflict = await conn.fetchrow("SELECT * FROM conflicts WHERE conflict_id = $1", item["ref_id"])
            old_fact = await conn.fetchrow(
                "SELECT field_value, quote FROM extracted_facts WHERE fact_id = $1", conflict["fact_id_old"]
            )
            new_fact = await conn.fetchrow(
                "SELECT field_value, quote FROM extracted_facts WHERE fact_id = $1", conflict["fact_id_new"]
            )
            item["old_value"] = old_fact["field_value"] if old_fact else None
            item["old_quote"] = old_fact["quote"] if old_fact else None
            item["new_value"] = new_fact["field_value"] if new_fact else None
            item["new_quote"] = new_fact["quote"] if new_fact else None
        items.append(item)
    return items

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
            action = "set"  # first time this field ever got a value, for the changelog
        else:  # item_type == "conflict"
            conflict = await conn.fetchrow(
                "SELECT * FROM conflicts WHERE conflict_id = $1",
                item["ref_id"],
            )
            # reviewer picks which side of the conflict wins, defaults
            # to the newer value if they didn't specify
            keep = decision.keep or "new"
            chosen_fact_id = conflict["fact_id_new"] if keep == "new" else conflict["fact_id_old"]
            action = "kept_new" if keep == "new" else "kept_old"  # for the changelog
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

        # append-only, this row is never touched again, it's what lets us answer "what changed, when, from what" without guessing.
        # action records WHICH decision produced this row (set/kept_new/
        # kept_old), used by the changelog to describe what happened
        await conn.execute(
            """INSERT INTO register_history (loan_file_id, field_name, old_fact_id, new_fact_id, action)
                VALUES ($1, $2, $3, $4, $5)""",
            item["loan_file_id"], item["field_name"],
            old["fact_id"] if old else None, chosen_fact_id, action,
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
    rows = await conn.fetch(    # latest result per rule only, findings table itself keeps full history
        """SELECT DISTINCT ON (rule_id) *
           FROM findings WHERE loan_file_id = $1
           ORDER BY rule_id, created_at DESC""",
        loan_file_id
    ) 
    return [dict(r) for r in rows]

async def list_changelog(conn, loan_file_id: str):
    approvals = await conn.fetch(
        """SELECT rh.history_id AS id, rh.field_name, rh.changed_at AS timestamp, rh.action,
                  d.file_path AS source_file
           FROM register_history rh
           LEFT JOIN extracted_facts ef ON ef.fact_id = rh.new_fact_id
           LEFT JOIN documents d ON d.document_id = ef.document_id
           WHERE rh.loan_file_id = $1""",
        loan_file_id,
    )
    decided = await conn.fetch(
        """SELECT rq.item_id AS id, rq.field_name, rq.decided_at AS timestamp, rq.status,
                  d.file_path AS source_file
           FROM review_queue rq
           LEFT JOIN extracted_facts ef ON ef.fact_id = (
               -- register_update items point straight at a fact, conflict
               -- items point at a conflict row, follow whichever applies
               CASE WHEN rq.item_type = 'register_update' THEN rq.ref_id
                    ELSE (SELECT fact_id_new FROM conflicts c WHERE c.conflict_id = rq.ref_id)
               END
           )
           LEFT JOIN documents d ON d.document_id = ef.document_id
           WHERE rq.loan_file_id = $1 AND rq.status IN ('rejected', 'superseded')""",
        loan_file_id,
    )

    entries = []
    for r in approvals:
        label = {"set": "approved", "kept_new": "kept new value", "kept_old": "kept old value"}.get(r["action"], r["action"])
        entries.append({
            "id": str(r["id"]), "field_name": r["field_name"], "timestamp": r["timestamp"].isoformat(),
            "description": f"{label}, from {r['source_file']}" if r["source_file"] else label,
        })
    for r in decided:
        entries.append({
            "id": str(r["id"]), "field_name": r["field_name"], "timestamp": r["timestamp"].isoformat(),
            "description": f"{r['status']}, from {r['source_file']}" if r["source_file"] else r["status"],
        })

    entries.sort(key=lambda e: e["timestamp"], reverse=True)
    return entries

async def _persist_cost_log(conn, run_id: str):
    for entry in drain_usage_log():
        await conn.execute(
            "INSERT INTO cost_log (run_id, stage, tokens_in, tokens_out, latency_ms) VALUES ($1, $2, $3, $4, $5)",
            run_id, entry["stage"], entry["tokens_in"], entry["tokens_out"], entry["latency_ms"],
        )

async def get_cost_report(conn, run_id: str):
    rows = await conn.fetch(
        """SELECT stage, sum(tokens_in) tokens_in, sum(tokens_out) tokens_out,
                  sum(latency_ms) latency_ms, count(*) call_count
           FROM cost_log WHERE run_id = $1 GROUP BY stage ORDER BY stage""",
        run_id,
    )
    return [dict(r) for r in rows]

async def get_loan_file_cost_report(conn, loan_file_id: str):   
    rows = await conn.fetch(
        """SELECT cl.stage, sum(cl.tokens_in) tokens_in, sum(cl.tokens_out) tokens_out,
                  sum(cl.latency_ms) latency_ms, count(*) call_count
           FROM cost_log cl JOIN runs r ON r.run_id = cl.run_id
           WHERE r.loan_file_id = $1 GROUP BY cl.stage ORDER BY cl.stage""",
        loan_file_id,
    )
    return [dict(r) for r in rows]

async def delete_loan_file(conn, loan_file_id: str):
    async with conn.transaction():
        # children before parents, foreign key constraints require this order
        await conn.execute("DELETE FROM cost_log WHERE run_id IN (SELECT run_id FROM runs WHERE loan_file_id = $1)", loan_file_id)
        await conn.execute("DELETE FROM review_queue WHERE loan_file_id = $1", loan_file_id)
        await conn.execute("DELETE FROM findings WHERE loan_file_id = $1", loan_file_id)
        await conn.execute("DELETE FROM conflicts WHERE loan_file_id = $1", loan_file_id)
        await conn.execute("DELETE FROM register_history WHERE loan_file_id = $1", loan_file_id)
        await conn.execute("DELETE FROM register WHERE loan_file_id = $1", loan_file_id)
        await conn.execute("DELETE FROM extracted_facts WHERE loan_file_id = $1", loan_file_id)
        await conn.execute("DELETE FROM runs WHERE loan_file_id = $1", loan_file_id)
        await conn.execute("DELETE FROM documents WHERE loan_file_id = $1", loan_file_id)
        await conn.execute("DELETE FROM loan_files WHERE loan_file_id = $1", loan_file_id)
    return {"deleted": loan_file_id}