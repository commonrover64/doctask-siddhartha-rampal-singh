import asyncio
import os
from pathlib import Path
import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ["DATABASE_URL"]

migrations_dir = Path(__file__).resolve().parent.parent.parent / "db" / "migrations"
async def run_migrations():

    conn = await asyncpg.connect(DATABASE_URL)

    try:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
        filename TEXT PRIMARY KEY,
        applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """)
        applied = {r["filename"] for r in await conn.fetch("SELECT filename FROM schema_migrations")}

        sql_files = sorted(migrations_dir.glob("*.sql"))

        for path in sql_files:
            if path.name in applied:
                print(f"skip (already applied): {path.name}")
                continue

            print(f"applying: {path.name}")
            sql = path.read_text()

            async with conn.transaction():

                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (filename) VALUES ($1)",
                    path.name
                )
                print(f" done")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(run_migrations())
