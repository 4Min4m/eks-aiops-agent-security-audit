"""The whole graph, in one file, because it's genuinely small: two nodes,
one edge. If this file ever grows past ~30 lines of actual graph-building
code, that's a signal you've drifted back toward the "multi-agent war room"
scope this project explicitly avoids — see PLAN-project4-aiops.md's
"Explicit non-goals" section.
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from .nodes.investigator import investigate
from .nodes.reporter import report
from .state import InvestigationState


def build_graph():
    graph = StateGraph(InvestigationState)

    graph.add_node("investigator", investigate)
    graph.add_node("reporter", report)

    graph.set_entry_point("investigator")
    graph.add_edge("investigator", "reporter")
    graph.add_edge("reporter", END)

    return graph.compile()


# Compiled once at import time; FastAPI's webhook handler reuses this.
compiled_graph = build_graph()
