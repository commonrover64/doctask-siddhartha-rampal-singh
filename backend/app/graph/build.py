"""Assembles the classification graph. Just one node today. this file's
whole job is to exist as the place where nodes get connected, so adding
the second node later is a small diff here, not a rewrite."""
from langgraph.graph import StateGraph, END
from app.graph.state import ClassifyState
from app.graph.nodes import classify_doc, flag_for_review, CONFIDENCE_THRESHOLD, extract_facts, reconcile_facts

def build_classify_graph():
    g = StateGraph(ClassifyState)
    g.add_node("classify_doc", classify_doc)
    g.add_node("flag_for_review", flag_for_review)
    g.add_node("extract_facts", extract_facts)
    g.add_node("reconcile_facts", reconcile_facts)
    g.set_entry_point("classify_doc")

    def route(state: dict) -> str:
        # This function is the actual "decision that changes the path."
        # LangGraph calls it after classify_doc finishes, with the
        # updated state, and uses the string it returns to pick the
        # next edge from the mapping below.
        if state["confidence"] < CONFIDENCE_THRESHOLD:
            return "low_confidence"
        return "high_confidence"

    g.add_conditional_edges(
        "classify_doc",
        route,
        {
            "low_confidence": "flag_for_review",
            "high_confidence": "extract_facts",
        }
    )

    g.add_edge("flag_for_review", "extract_facts")
    g.add_edge("extract_facts", "reconcile_facts")
    g.add_edge("reconcile_facts", END)
    
    return g.compile()
    # .compile() turns the graph definition into something actually
    # runnable — you call .ainvoke(state) on the result.