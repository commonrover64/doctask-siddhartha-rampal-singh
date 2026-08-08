import os
import asyncpg
from dotenv import load_dotenv

load_dotenv() # reads .env into enviromnet variables

DATABASE_URL = os.environ["DATABSE_URL"]
_pool: asyncpg.Pool | None = None

async def get_pool() -> asyncpg.Pool:

    """Lazily creates one shared connection pool for the whole app.
    We don't want a new connection per-request, that will be slow"""

    global _pool 

    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)

    return _pool