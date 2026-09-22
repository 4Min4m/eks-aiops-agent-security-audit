"""Phase 3 — instrument the agent with Grafana Agent Observability
(`agento11y`, formerly the `sigil-sdk` / "Grafana Sigil SDK" referenced in
the original project idea).

Naming note: Grafana renamed this product mid-2026 from `sigil-sdk` to
`agento11y` (Grafana Agent Observability). The underlying APIs are
unchanged — only the package/import name moved. This file, and this
project, targets the current name. If you're reading this months later and
`agento11y` looks unfamiliar too, check Grafana's docs for whatever it's
called by then; the instrumentation pattern below (a context manager around
each node's LLM call, tagged with node name) should still translate
directly.

Meta note worth keeping in the README, not hiding: this project uses
observability tooling to observe the AI agent that itself investigates
observability alerts. That's a genuinely useful thing to point out in an
interview, not a gimmick to oversell.
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Iterator

try:
    from agento11y import AgentTracer  # type: ignore
except ImportError:  # pragma: no cover
    # Golden-copy safety net: if agento11y isn't installed yet (e.g. you're
    # running the graph locally before wiring Phase 3), instrumentation
    # becomes a no-op instead of crashing the whole agent. Remove this
    # fallback once agento11y is actually installed and configured.
    AgentTracer = None  # type: ignore


_tracer = None
if AgentTracer is not None:
    _tracer = AgentTracer(
        service_name=os.environ.get("AGENTO11Y_SERVICE_NAME", "aiops-investigator-agent"),
        endpoint=os.environ.get("AGENTO11Y_ENDPOINT", ""),
    )


@contextmanager
def trace_node(node_name: str) -> Iterator[None]:
    """Wrap a graph node's LLM call so its latency and generation count show
    up in Grafana's AI Observability / Conversations view.

    No cost dimension is emitted here — the agent runs against local
    Ollama, not a paid API, so there's nothing to bill. Latency and
    generation counts are still meaningful signals on their own (e.g.
    "the Investigator node is the slow one because Loki queries are
    unindexed" is a real, demoable finding).
    """
    started = time.monotonic()
    if _tracer is None:
        yield
        return
    with _tracer.trace(node=node_name):
        yield
    elapsed = time.monotonic() - started
    _tracer.record_latency(node=node_name, seconds=elapsed)
