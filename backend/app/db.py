import os
import asyncpg
from dotenv import load_dotenv
import contextlib

load_dotenv() # reads .env into enviromnet variables

DATABASE_URL = os.environ["DATABASE_URL"]
_pool: asyncpg.Pool | None = None

async def get_pool() -> asyncpg.Pool:

    """Lazily creates one shared connection pool for the whole app.
    We don't want a new connection per-request, that will be slow"""

    global _pool 

    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)

    return _pool

@contextlib.asynccontextmanager
async def loan_file_lock(loan_file_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():   # the lock lives inside this transaction now
            print(f"[Lock] acquiring for {loan_file_id}")
            await conn.execute(         # hashtextextended is computed by Postgres itself, deterministic across every process that connects to the same database
                "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", 
                loan_file_id
            )
            print(f"[lock] acquired {loan_file_id}")
            yield conn
            print(f"[lock] releasing {loan_file_id}")
            # lock is released automatically here, on commit AND on error/rollback
        