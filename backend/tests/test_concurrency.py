"""Proves loan_file_lock serializes runs against the same loan file while
leaving different loan files fully parallel."""
import asyncio
import time
import uuid
import pytest
from app.db import loan_file_lock


@pytest.mark.asyncio
async def test_same_loan_file_serializes(loan_file):
    order = []

    async def hold(tag: str, seconds: float):
        async with loan_file_lock(loan_file):
            order.append(f"{tag}-start")
            await asyncio.sleep(seconds)
            order.append(f"{tag}-end")

    await asyncio.gather(hold("A", 0.3), hold("B", 0.1))
    assert order == ["A-start", "A-end", "B-start", "B-end"]  # B never starts until A fully finishes


@pytest.mark.asyncio
async def test_different_loan_files_run_in_parallel(pool):
    pile_a, pile_b = str(uuid.uuid4()), str(uuid.uuid4())
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO loan_files (loan_file_id, borrower_name) VALUES ($1, 'A')", pile_a)
        await conn.execute("INSERT INTO loan_files (loan_file_id, borrower_name) VALUES ($1, 'B')", pile_b)

    started = {}

    async def hold(pid: str, tag: str):
        async with loan_file_lock(pid):
            started[tag] = time.monotonic()
            await asyncio.sleep(0.3)

    t0 = time.monotonic()
    await asyncio.gather(hold(pile_a, "A"), hold(pile_b, "B"))

    assert abs(started["A"] - started["B"]) < 0.1  # both started close together, neither waited on the other

    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM loan_files WHERE loan_file_id IN ($1, $2)", pile_a, pile_b)