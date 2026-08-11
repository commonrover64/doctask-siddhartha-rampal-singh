"""Shared logic, called by both the REST routes in main.py and the MCP
tools in mcp_server.py. Neither one contains real logic itself, they're
both thin wrappers around these functions, so a human using /docs and a
program using MCP always get identical behavior."""

from app.rules import run_playbook

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
    return [dict[r] for r in rows]
