"""Assembles the classification graph. Just one node today. this file's
whole job is to exist as the place where nodes get connected, so adding
the second node later is a small diff here, not a rewrite."""
from langgraph.graph import StateGraph, END
from app.graph.state import ClassifyState
from app.graph.nodes import classify_doc

def build_classify_graph():
    g = StateGraph(ClassifyState)
    g.add_node("classify_doc", classify_doc)
    g.set_entry_point("classify_doc")
    g.add_edge("classify_doc", END)
    # add_edge("classify_doc", END) means: after this node runs, the
    # graph is done. With a second node later, this becomes
    # add_edge("classify_doc", "next_node") instead.
    return g.compile()
    # .compile() turns the graph definition into something actually
    # runnable — you call .ainvoke(state) on the result.