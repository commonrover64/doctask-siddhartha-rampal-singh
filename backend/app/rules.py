"""Loads the playbook and runs each rule against a loan file. Each rule's
'check' name maps to a Python function in CHECK_FUNCTIONS below, adding a
new rule type means adding one function here and one entry in the dict."""

import yaml
from pathlib import Path

PLAYBOOK_PATH = Path(__file__).resolve().parent / "playbook.yaml"

# print(PLAYBOOK_PATH)

async def check_required_doc_types_present(conn, loan_file_id: str, params: dict) -> dict:
    required = params["required"]
    rows = await conn.fetch(
        "SELECT DISTINCT doc_type FROM documents WHERE loan_file_id = $1", 
        loan_file_id
    )
    present = {r["doc_type"] for r in rows} # set, for fast lookup below
    missing = [d for d in required if d not in present]

    if missing:
        return {
            "status": "violation",
            "detail": f"Missing required document types: {','.join(missing)}",
        }
    return {
        "status": "clean",
        "detail": "All required document types are present.",
    }

async def run_playbook(conn, loan_file_id: str) -> list[dict]:
    playbook = yaml.safe_load(PLAYBOOK_PATH.read_text())
    findings = []

    for rule in playbook["rules"]:
        check_fn = CHECK_FUNCTIONS.get(rule["check"])

        if check_fn is None:
            # unknown check type, don't crash the whole run, report it as inconclusive so it's visible instead of silently skipped
            result = {
                "status": "inconclusive",
                "detail": f"Unknown check type: {rule["check"]}"
            }
        else:
            result = await check_fn(conn, loan_file_id, rule.get("params", {}))

        finding_id = await conn.fetchval(
            """INSERT INTO findings (loan_file_id, stage, rule_id, status, detail)
            VALUES ($1, $2, $3, $4, $5) RETURNING finding_id""",
            loan_file_id, rule["stage"], rule["id"], result["status"], result["detail"],
        )

        findings.append({
            "finding_id": str(finding_id),
            "rule_id": rule["id"],
            "stage": rule["stage"],
            **result,
        })
    return findings

async def check_loan_amount_consistent(conn, loan_file_id: str, params: dict) -> dict:
    """accuracy: the register's loan_amount should not still show a value
    from before the most recent amendment, if one exists."""
    amendment_exists = await conn.fetchval(
        "SELECT count(*) FROM documents WHERE loan_file_id = $1 AND doc_type = 'amendment'",
        loan_file_id,
    ) 
    if not amendment_exists:
        return {
            "status": "clean",
            "detail": "No amendment on file, nothing to check."
        }
    open_conflict = await conn.fetchrow(
        "SELECT * FROM conflicts WHERE loan_file_id = $1 AND field_name = 'loan_amount' AND status = 'open'",
        loan_file_id
    )
    if open_conflict:
        return {
            "status": "violation",
            "detail": "Loan amount has an unresolved conflict, likely from an amendment not yet reflected in the register.",
        }
    return {
        "status": "clean", 
        "detail": "loan_amount has no unresolved conflicts."
    }

async def check_no_embedded_instruction(conn, loan_file_id: str, params:dict) -> dict:
    """consistency: no source document should contain text trying to
    direct the system's behavior."""

    patterns = ["ignore previous instructions", "ignore all previous", "you are now",
                "disregard the above", "system:", "new instructions"]
    rows = await conn.fetch(
        "SELECT document_id, raw_text FROM documents WHERE loan_file_id = $1", loan_file_id
    )
    hits = []

    for row in rows:
        text_lower = (row["raw_text"] or "").lower()

        for pattern in patterns:
            if pattern in text_lower:
                hits.append(f"document {row['document_id']}: contains  '{pattern}'")

    if hits:
        return {
            "status": "violation",
            "detail": "; ".join(hits)
        }
    return {
        "status": "clean",
        "detail": "No embedded instructions found in any document"
    }

async def check_appraisal_recency(conn, loan_file_id: str, params: dict) -> dict:
    """regulatory: appraisal_date fact should be within max_days of
    application_date fact, both pulled from the register (approved
    values only)."""
    import datetime
    max_days = params.get("max_days", 120)

    rows = await conn.fetch(
        """SELECT r.field_name, ef.field_value FROM register r
           JOIN extracted_facts ef ON ef.fact_id = r.fact_id
           WHERE r.loan_file_id = $1 AND r.field_name IN ('appraisal_date', 'application_date')""",
        loan_file_id,
    )
    values = {r["field_name"]: r["field_value"] for r in rows}

    if "appraisal_date" not in values or "application_date" not in values:
        return {
            "status": "inconclusive", 
            "detail": "appraisal_date or application_date not yet approved in register."
        }

    try:
        appraisal_date = datetime.date.fromisoformat(values["appraisal_date"])
        application_date = datetime.date.fromisoformat(values["application_date"])
    except ValueError:
        return {
            "status": "inconclusive", 
            "detail": "Could not parse one of the dates."
        }

    days_apart = abs((application_date - appraisal_date).days)
    if days_apart > max_days:
        return {
            "status": "violation", 
            "detail": f"Appraisal is {days_apart} days from application date, exceeds {max_days} day limit."
        }
    return {
        "status": "clean", 
        "detail": f"Appraisal is {days_apart} days from application date, within {max_days} day limit."
    }


CHECK_FUNCTIONS = {
    "required_doc_types_present": check_required_doc_types_present,
    "loan_amount_consistent": check_loan_amount_consistent,
    "no_embedded_instructions": check_no_embedded_instruction,
    "appraisal_recency": check_appraisal_recency,
}