"""Read-only Loki query client. Pulls recent logs for the affected pod.

Note: this queries Loki for *application* logs (the pod's own stdout/
stderr), which is a different stream than the k8s-audit stream Phase 1
ships to the same Loki instance. Both live in the same Loki, distinguished
by the `source` label — this client filters to pod logs only via the
namespace/pod labels the default Kubernetes log collection sets.
"""
from __future__ import annotations

import os
import time
from urllib.parse import quote

import httpx

_BASE_URL = os.environ.get("LOKI_BASE_URL", "http://loki-gateway.monitoring.svc.cluster.local")


def query_recent_pod_logs(namespace: str, pod: str, lookback_minutes: int = 15, limit: int = 200) -> str:
    """Return the last `limit` log lines for `pod` in `namespace`, newest
    last, as a single newline-joined string ready to drop into a prompt.
    """
    now_ns = time.time_ns()
    start_ns = now_ns - (lookback_minutes * 60 * 1_000_000_000)

    logql = f'{{namespace="{namespace}", pod="{pod}"}}'
    params = {
        "query": logql,
        "start": str(start_ns),
        "end": str(now_ns),
        "limit": str(limit),
        "direction": "backward",
    }

    try:
        resp = httpx.get(
            f"{_BASE_URL}/loki/api/v1/query_range",
            params=params,
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        return f"[loki query failed: {exc}]"

    lines: list[str] = []
    for stream in data.get("data", {}).get("result", []):
        for _ts, line in stream.get("values", []):
            lines.append(line)

    if not lines:
        return "[no log lines found in the lookback window — pod may be crashing before it logs anything]"

    # Loki returns backward (newest first); reverse for a natural read order.
    return "\n".join(reversed(lines[-limit:]))
