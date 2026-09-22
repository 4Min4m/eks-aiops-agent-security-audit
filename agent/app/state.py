"""State schema shared by both graph nodes.

Deliberately flat and small — this is a two-node graph, not a multi-agent
system with a sprawling shared-memory blob. Every field here is either
input (the alert), evidence gathered by the Investigator, or the final
output produced by the Reporter.
"""
from __future__ import annotations

from typing import TypedDict


class AlertPayload(TypedDict):
    """The subset of an Alertmanager webhook payload we actually use."""
    alertname: str
    namespace: str
    pod: str
    container: str
    summary: str
    description: str
    starts_at: str


class Evidence(TypedDict, total=False):
    """What the Investigator node gathers before handing off."""
    recent_logs: str          # from Loki
    restart_count_series: str  # from Prometheus, human-readable summary
    describe_output: str      # `kubectl describe pod` equivalent, via API


class InvestigationState(TypedDict, total=False):
    alert: AlertPayload
    evidence: Evidence
    summary_markdown: str      # Reporter node's final output
    report_path: str           # where it was written on disk
