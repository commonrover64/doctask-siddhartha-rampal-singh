"""Proves a run interrupted after classify_doc resumes without re-running
that node, using the same Postgres checkpoint a real crash would leave."""
import pytest
from app.graph.checkpointer import get_checkpointer
from app.graph.build import build_classify_graph
from app.llm import set_override
from tests.helpers import make_document

call_log = []  # module-level, cleared at the start of each test run

async def counting_llm(system: str, prompt: str) -> str:
    call_log.append(system[:20])  # just enough to tell classify vs extract apart
    if "classify" in system.lower():
        return '{"doc_type": "application", "confidence": 0.95}'
    return '{"fields": []}'


@pytest.mark.asyncio
async def test_resume_does_not_rerun_finished_nodes(pool, loan_file):
    call_log.clear()
    document_id = await make_document(pool, loan_file, "Loan Application: amount $250,000", "app.txt")

    checkpointer = await get_checkpointer()

    set_override(counting_llm)
    try:
        interrupted_graph = build_classify_graph(checkpointer, interrupt_after=["classify_doc"])
        thread_id = "test-resume-thread"
        config = {"configurable": {"thread_id": thread_id}}

        await interrupted_graph.ainvoke({
            "document_id": document_id, "loan_file_id": loan_file, "raw_text": "Loan Application: amount $250,000",
            "doc_type": "", "confidence": 0.0, "needs_review": False,
            "facts": [], "existing_facts": {}, "conflicts": [],
        }, config=config)

        calls_after_interrupt = len(call_log)
        assert calls_after_interrupt == 1  # only classify_doc ran so far

        full_graph = build_classify_graph(checkpointer)  # no interrupt this time, runs to completion
        await full_graph.ainvoke(None, config=config)  # None input = resume from last checkpoint

        assert len(call_log) > calls_after_interrupt  # extract_facts should have run during resume
        resumed_calls = call_log[calls_after_interrupt:]
        assert call_log[0] not in resumed_calls  # classify_doc's prompt must not appear again
    finally:
        set_override(None)