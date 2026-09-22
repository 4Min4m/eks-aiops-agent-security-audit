"""Reporter node — the second and final node in this graph.

Turns gathered evidence into a structured summary: likely cause, evidence
for it, and a suggested *next diagnostic step* — deliberately not an
automatic fix. This is the read-only safety boundary made concrete: the
agent is not allowed to conclude "and so I ran X to fix it," because it has
no tool to run X with in the first place (see kubectl_client.py — no write
methods exist).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from ..llm import get_llm
from ..observability import trace_node
from ..state import InvestigationState

_REPORT_DIR = os.environ.get("REPORT_OUTPUT_DIR", "./incident-reports")

_SYSTEM_PROMPT = """You are an incident-investigation assistant for a Kubernetes cluster.
You are given an alert and evidence gathered about it (logs, a restart-count
metric, and a pod describe). Produce a concise Markdown report with exactly
these three sections:

## Likely cause
One or two sentences. Be direct; say "unclear from available evidence" if
the evidence genuinely doesn't point anywhere specific rather than guessing.

## Evidence
Bullet points citing specific facts from the logs/metrics/describe output
you were given — do not invent details that aren't in the evidence.

## Suggested next diagnostic step
ONE concrete next step a human should take to confirm or narrow down the
cause. This must be a read-only diagnostic action (e.g. "check the
ConfigMap referenced by this pod's volume mounts"), never a remediation
action (never "restart the pod", "scale the deployment", "roll back",
etc.) — you do not have the authority or the tooling to take those actions,
and neither should this report suggest taking them automatically.
"""


def _build_user_prompt(state: InvestigationState) -> str:
    alert = state["alert"]
    evidence = state["evidence"]
    return f"""Alert: {alert['alertname']}
Namespace: {alert['namespace']}
Pod: {alert['pod']}
Container: {alert['container']}
Alert description: {alert['description']}

--- Recent logs ---
{evidence['recent_logs']}

--- Restart count ---
{evidence['restart_count_series']}

--- Pod describe ---
{evidence['describe_output']}
"""


def report(state: InvestigationState) -> InvestigationState:
    llm = get_llm()

    with trace_node("reporter"):
        response = llm.invoke(
            [
                ("system", _SYSTEM_PROMPT),
                ("human", _build_user_prompt(state)),
            ]
        )
    summary_markdown = response.content

    Path(_REPORT_DIR).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    alert = state["alert"]
    filename = f"{timestamp}_{alert['alertname']}_{alert['pod']}.md"
    report_path = str(Path(_REPORT_DIR) / filename)

    header = (
        f"# Incident report: {alert['alertname']}\n\n"
        f"- Namespace: `{alert['namespace']}`\n"
        f"- Pod: `{alert['pod']}`\n"
        f"- Alert fired at: {alert['starts_at']}\n"
        f"- Report generated: {timestamp}\n\n---\n\n"
    )
    Path(report_path).write_text(header + summary_markdown, encoding="utf-8")

    return {**state, "summary_markdown": summary_markdown, "report_path": report_path}
