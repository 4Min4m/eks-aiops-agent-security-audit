"""Read-only Prometheus query client. Pulls the pod's restart-count series
so the Reporter can cite something concrete ("4 restarts in the last 10
minutes") instead of the LLM inventing a number.
"""
from __future__ import annotations

import os

import httpx

_BASE_URL = os.environ.get(
    "PROMETHEUS_BASE_URL",
    "http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090",
)


def query_restart_count(namespace: str, pod: str) -> str:
    """Return a short human-readable summary of the container restart count
    for `pod`, using kube-state-metrics (already deployed by Project 1's
    kube-prometheus-stack).
    """
    promql = f'kube_pod_container_status_restarts_total{{namespace="{namespace}", pod="{pod}"}}'

    try:
        resp = httpx.get(
            f"{_BASE_URL}/api/v1/query",
            params={"query": promql},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        return f"[prometheus query failed: {exc}]"

    results = data.get("data", {}).get("result", [])
    if not results:
        return f"[no restart-count series found for pod={pod} namespace={namespace}]"

    lines = []
    for series in results:
        container = series.get("metric", {}).get("container", "unknown")
        value = series.get("value", [None, "?"])[1]
        lines.append(f"container={container} restarts_total={value}")

    return "; ".join(lines)
