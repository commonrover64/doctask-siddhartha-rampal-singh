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

CHECK_FUNCTIONS = {
    "required_doc_types_present": check_required_doc_types_present,
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