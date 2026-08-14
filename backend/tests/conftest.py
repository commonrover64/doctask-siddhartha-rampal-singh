"""Shared fixtures. Every test gets a fresh loan_file_id, and everything
created under it gets deleted afterward, in foreignkey safe order, so tests never
leave junk behind in the real Neon database."""
import uuid
import pytest, pytest_asyncio
from app.db import get_pool

@pytest_asyncio.fixture
async def pool():
    return await get_pool()

@pytest_asyncio.fixture
async def loan_file(pool):
    loan_file_id = str(uuid.uuid4())
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO loan_files (loan_file_id, borrower_name) VALUES ($1, $2)",
            loan_file_id, "Test Borrower"
        )
    yield loan_file_id      # test runs here

    # removing residue from test, foreign key order matters: children before parents
    async with pool.acquire() as conn:      
        await conn.execute("DELETE FROM review_queue WHERE loan_file_id = $1", loan_file_id)
        await conn.execute("DELETE FROM findings WHERE loan_file_id = $1", loan_file_id)
        await conn.execute("DELETE FROM conflicts WHERE loan_file_id = $1", loan_file_id)
        await conn.execute("DELETE FROM register_history WHERE loan_file_id = $1", loan_file_id)
        await conn.execute("DELETE FROM register WHERE loan_file_id = $1", loan_file_id)
        await conn.execute("DELETE FROM extracted_facts WHERE loan_file_id = $1", loan_file_id)
        await conn.execute("DELETE FROM runs WHERE loan_file_id = $1", loan_file_id)
        await conn.execute("DELETE FROM documents WHERE loan_file_id = $1", loan_file_id)
        await conn.execute("DELETE FROM loan_files WHERE loan_file_id = $1", loan_file_id)