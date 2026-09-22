"""Webhook receiver: Alertmanager POSTs here, we run the graph, we write a
report file. No chat UI, no polling — Alertmanager pushes, we react. This
matches the plan's "real, inspectable output artifact, not a live chat demo
that only works when someone's watching."
"""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI, Request

from .graph import compiled_graph
from .state import AlertPayload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aiops-agent")

app = FastAPI(title="AIOps Investigator Agent")

_TARGET_NAMESPACE = os.environ.get("TARGET_NAMESPACE", "httpbin")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/webhook/alertmanager")
async def alertmanager_webhook(request: Request):
    """Alertmanager's webhook payload contains one or more `alerts`, each
    with `labels` and `annotations`. We only act on alerts matching the
    one scenario this agent knows how to investigate (Phase 0's scope
    decision) — anything else is acknowledged but skipped, not guessed at.
    """
    payload = await request.json()
    results = []

    for alert in payload.get("alerts", []):
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})

        if labels.get("alertname") != "PodCrashLoopBackOff":
            logger.info("Skipping alert %s — outside this agent's scope", labels.get("alertname"))
            continue

        if labels.get("namespace") != _TARGET_NAMESPACE:
            logger.info("Skipping alert in namespace %s — outside TARGET_NAMESPACE", labels.get("namespace"))
            continue

        alert_input: AlertPayload = {
            "alertname": labels.get("alertname", "unknown"),
            "namespace": labels.get("namespace", "unknown"),
            "pod": labels.get("pod", "unknown"),
            "container": labels.get("container", "unknown"),
            "summary": annotations.get("summary", ""),
            "description": annotations.get("description", ""),
            "starts_at": alert.get("startsAt", ""),
        }

        logger.info("Investigating %s / %s", alert_input["namespace"], alert_input["pod"])
        final_state = compiled_graph.invoke({"alert": alert_input})
        results.append({"pod": alert_input["pod"], "report_path": final_state["report_path"]})

    return {"processed": results}
