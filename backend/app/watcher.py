"""Watches watched_incoming/ for new files. On a new file, ingests it as a
document (same dedup-by-hash logic as the upload endpoint) and runs the
pipeline on just that one document, not the whole loan file, not the
whole corpus. Run standalone: python -m app.watcher"""

import asyncio
import hashlib
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from app.db import get_pool
from app.graph.checkpointer import get_checkpointer
from app.graph.build import build_classify_graph
from app.operations import process_document_op, set_graph

WATCHED_DIR = Path(__file__).resolve().parent.parent / "watched_incoming"

async def ingest_and_process(file_path: Path):
    loan_file_id = file_path.parent.name       # folder name = loan file id
    text = file_path.read_text()
    content_hash = hashlib.sha256(text.encode()).hexdigest()

    pool = await get_pool()
    async with pool.acquire() as conn:
        document_id = await conn.fetchval(
            """INSERT INTO documents (loan_file_id, file_path, raw_text, content_hash)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (loan_file_id, content_hash) DO NOTHING
               RETURNING document_id""",
            loan_file_id, str(file_path), text, content_hash,
        )
        if document_id is None:
            print(f"skip (duplicate content): {file_path.name}")
            return

    print(f"new document {document_id} for loan_file {loan_file_id}, processing...")
    result = await process_document_op(pool, str(document_id))
    print(f"done: {result.get('run_id')}, facts extracted: {len(result.get('facts', []))}")

class Handler(FileSystemEventHandler):
    def __init__(self, loop):
        self.loop = loop # watchdog callbacks are sync, need this to call back into async code

    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith(".txt"):
            return
        asyncio.run_coroutine_threadsafe(ingest_and_process(Path(event.src_path)), self.loop)

async def main():
    checkpointer = await get_checkpointer()
    graph = build_classify_graph(checkpointer)
    set_graph(graph)    # watcher builds its own graph, separate process from uvicorn

    loop = asyncio._get_running_loop()
    observer = Observer()
    observer.schedule(Handler(loop), str(WATCHED_DIR), recursive=True)
    observer.start()
    print(f"Watching {WATCHED_DIR} for new documents...")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    asyncio.run(main())