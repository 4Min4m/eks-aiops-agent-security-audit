"""Investigator node — the first of exactly two nodes in this graph.

Given an alert, pulls the context a human on-call engineer would pull
first: recent logs, the restart-count metric, and a pod describe. Does NOT
call the LLM to interpret anything yet — that's the Reporter's job. Keeping
"gather evidence" and "explain evidence" as separate nodes is what makes
this a graph worth drawing rather than one big function; it also means you
can unit-test evidence-gathering without needing a model running at all.
"""
from __future__ import annotations

from ..observability import trace_tool
from ..state import InvestigationState
from ..tools.kubectl_client import describe_pod
from ..tools.loki_client import query_recent_pod_logs
from ..tools.prometheus_client import query_restart_count


def investigate(state: InvestigationState) -> InvestigationState:
    alert = state["alert"]
    namespace = alert["namespace"]
    pod = alert["pod"]

    args = {"namespace": namespace, "pod": pod}
    evidence = {}
    with trace_tool("loki_recent_pod_logs", args):
        evidence["recent_logs"] = query_recent_pod_logs(namespace, pod)
    with trace_tool("prometheus_restart_count", args):
        evidence["restart_count_series"] = query_restart_count(namespace, pod)
    with trace_tool("k8s_describe_pod", args):
        evidence["describe_output"] = describe_pod(namespace, pod)

    return {**state, "evidence": evidence}
