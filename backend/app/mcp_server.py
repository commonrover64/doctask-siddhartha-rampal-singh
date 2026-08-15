"""MCP server, the machine interface. Every tool here calls the same
shared function main.py's REST route calls, see app/operations.py."""

from fastmcp import FastMCP
from app.db import get_pool
from app.operations import get_register, list_pending, list_facts, list_conflicts, decide_review_item, list_changelog, get_cost_report
from app.schemas import ReviewDecision

mcp = FastMCP("loanfile-agent")

@mcp.tool()
async def get_register_tool(loan_file_id: str) -> list[dict]:
    """Returns the current approved register for a loan file, field name,
    value, source quote, and when it was last updated."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await get_register(conn, loan_file_id)

@mcp.tool()
async def list_pending_reviews(loan_file_id: str) -> list[dict]:
    """Returns pending review items (conflicts and register updates)
    awaiting human approval for a loan file."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await list_pending(conn, loan_file_id)

@mcp.tool()
async def get_facts(loan_file_id: str) -> list[dict]:
    """Returns every extracted fact for a loan file, including ones not
    yet approved into the register."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await list_facts(conn, loan_file_id)

@mcp.tool()
async def get_conflicts(loan_file_id: str) -> list[dict]:
    """Returns open and resolved conflicts for a loan file."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await list_conflicts(conn, loan_file_id)

@mcp.tool()
async def decide_review_item_tool(item_id: str, decision: str, keep: str = None) -> dict:
    """Approves or rejects a pending review item. decision must be
    'approve' or 'reject'. keep is only used for conflict items, 'old'
    or 'new', defaults to 'new' if not given. This is the explicit
    approval operation, nothing gets written to the register without
    this being called."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await decide_review_item(conn, item_id, ReviewDecision(decision=decision, keep=keep))

@mcp.tool()
async def get_changelog(loan_file_id: str) -> list[dict]:
    """Returns the register change history for a loan file, what changed,
    when, and from what value to what value."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await list_changelog(conn, loan_file_id)

@mcp.tool()
async def get_cost_report_tool(run_id: str) -> list[dict]:
    """Returns token usage and latency for a run, broken down by stage."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await get_cost_report(conn, run_id)

if __name__ == "__main__":
    mcp.run()