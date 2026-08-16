"""MCP server, the machine interface. Every tool here calls the same
shared function main.py's REST route calls, see app/operations.py."""

import asyncio
from app.graph.checkpointer import get_checkpointer
from app.graph.build import build_classify_graph
from fastmcp import FastMCP
from app.db import get_pool
from app.operations import (
    get_register, list_pending, list_facts, list_conflicts, decide_review_item, 
    list_changelog, get_cost_report, process_document_op, resume_run_op, set_graph
    )
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

@mcp.tool()
async def process_document_tool(document_id: str) -> dict:
    """Runs the classify/extract/reconcile pipeline on a document. Same
    operation as REST POST /documents/{id}/process and the watcher use,
    all three call process_document_op directly."""
    pool = await get_pool()
    return await process_document_op(pool, document_id)


@mcp.tool()
async def resume_run_tool(run_id: str) -> dict:
    """Resumes an interrupted run from its last LangGraph checkpoint. Same
    operation as REST POST /runs/{id}/resume."""
    pool = await get_pool()
    return await resume_run_op(pool, run_id)

async def _startup():
    checkpointer = await get_checkpointer()
    graph = build_classify_graph(checkpointer)
    set_graph(graph)

if __name__ == "__main__":
    mcp.run()