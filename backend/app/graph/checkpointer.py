"""Sets up the Postgres-backed checkpointer LangGraph uses to persist state
after every node completes. This is the entire mechanism behind
resumability, no custom save/resume logic needed, LangGraph handles it
once the graph is compiled with this."""

import os
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ["DATABASE_URL"]

_saver = None       # stores the active checkpointer
_saver_cm = None    # stores the async context manager


async def get_checkpointer():
    global _saver, _saver_cm

    if _saver is None:  # create checkpointer only once
        _saver_cm = AsyncPostgresSaver.from_conn_string(DATABASE_URL)
        _saver = await _saver_cm.__aenter__()  # open Postgresqlconnection

        # create checkpoint tables if they don't exist
        await _saver.setup()

    return _saver  # returns the ready to use checkpointer