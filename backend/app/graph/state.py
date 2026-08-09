from typing import TypedDict

class ClassifyState(TypedDict):
    """Everything that flows through the graph for one classification run.
    TypedDict (not a Pydantic model) is what LangGraph expects. its just
    a dict with type hints, so nodes read/write plain dict keys."""
    document_id: str      # which document we're classifying
    raw_text: str          # its content, fetched before the graph starts
    doc_type: str          # the node fills this in
    confidence: float      # the node fills this in too