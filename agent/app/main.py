"""Webhook receiver: Alertmanager POSTs here, we run the graph, we write a
report file. No chat UI, no polling — Alertmanager pushes, we react.
"""
from __future__ import annotations

import logging
import os
import re

from fastapi import FastAPI, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from .graph import compiled_graph
from .state import AlertPayload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aiops-agent")

app = FastAPI(title="AIOps Investigator Agent")

_TARGET_NAMESPACE = os.environ.get("TARGET_NAMESPACE", "httpbin")

# Kubernetes object names (DNS-1123 subdomain). Label values from the webhook
# are untrusted input: they end up in a LogQL query, a PromQL query and a
# report filename, so anything that isn't a valid pod/container name is
# rejected rather than interpolated.
_K8S_NAME = re.compile(r"^[a-z0-9]([-a-z0-9.]{0,251}[a-z0-9])?$")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/webhook/alertmanager")
async def alertmanager_webhook(request: Request):
    """Alertmanager's webhook payload contains one or more `alerts`, each
    with `labels` and `annotations`. We only act on firing alerts matching
    the one scenario this agent knows how to investigate — anything else is
    acknowledged but skipped, not guessed at.
    """
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="body must be JSON")

    results = []
    for alert in payload.get("alerts", []):
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})

        if alert.get("status", "firing") != "firing":
            continue

        if labels.get("alertname") != "PodCrashLoopBackOff":
            logger.info("Skipping alert %s — outside this agent's scope", labels.get("alertname"))
            continue

        if labels.get("namespace") != _TARGET_NAMESPACE:
            logger.info("Skipping alert in namespace %s — outside TARGET_NAMESPACE", labels.get("namespace"))
            continue

        pod = labels.get("pod", "")
        container = labels.get("container", "unknown")
        if not _K8S_NAME.match(pod) or not _K8S_NAME.match(container):
            logger.warning("Skipping alert with invalid pod/container label: %r / %r", pod, container)
            continue

        alert_input: AlertPayload = {
            "alertname": labels["alertname"],
            "namespace": labels["namespace"],
            "pod": pod,
            "container": container,
            "summary": annotations.get("summary", ""),
            "description": annotations.get("description", ""),
            "starts_at": alert.get("startsAt", ""),
        }

        logger.info("Investigating %s / %s", alert_input["namespace"], pod)
        try:
            # The graph is synchronous and the LLM call can take tens of
            # seconds on CPU; run it off the event loop so /healthz and other
            # requests stay responsive.
            final_state = await run_in_threadpool(compiled_graph.invoke, {"alert": alert_input})
        except Exception as exc:  # report the failure, keep processing other alerts
            logger.exception("Investigation failed for %s", pod)
            results.append({"pod": pod, "error": str(exc)})
            continue
        results.append({"pod": pod, "report_path": final_state["report_path"]})

    return {"processed": results}
