"""Phase 3 — instrument the agent with Grafana Agent Observability
(`agento11y`, formerly the `sigil-sdk` / "Grafana Sigil SDK").

Two things are recorded per investigation:

  * Tool executions — each evidence query the Investigator node makes
    (Loki, Prometheus, Kubernetes API) is recorded with its latency, so the
    "which data source is slow" question is answerable from Grafana.
  * Generations — the Reporter node's LLM call is recorded through the
    official LangChain callback handler (`agento11y-langchain`), which
    captures model, latency and token usage.

No cost dimension is emitted: the agent runs against a local Ollama model,
so there is nothing to bill. Latency and generation counts are still
meaningful signals on their own.

Configuration comes from the SDK's standard environment variables
(`AGENTO11Y_ENDPOINT`, `AGENTO11Y_AUTH_*`, ...). When `AGENTO11Y_ENDPOINT`
is unset, instrumentation is disabled and every helper here is a no-op, so
the agent still runs locally without an observability backend.

Meta note: this project uses observability tooling to observe the AI agent
that itself investigates observability alerts.
"""
from __future__ import annotations

import atexit
import logging
import os
from contextlib import contextmanager
from typing import Any, Iterator

logger = logging.getLogger("aiops-agent.observability")

AGENT_NAME = os.environ.get("AGENTO11Y_SERVICE_NAME", "aiops-investigator-agent")

_client = None
if os.environ.get("AGENTO11Y_ENDPOINT", "").strip():
    try:
        from agento11y import Client, ToolExecutionEnd, ToolExecutionStart
        from agento11y_langchain import with_agento11y_langchain_callbacks

        _client = Client()
        atexit.register(_client.shutdown)
        logger.info("agento11y instrumentation enabled (agent_name=%s)", AGENT_NAME)
    except Exception:  # pragma: no cover - never let telemetry take the agent down
        logger.exception("agento11y could not be initialised; continuing without instrumentation")
        _client = None
else:
    logger.info("AGENTO11Y_ENDPOINT not set; agento11y instrumentation disabled")


@contextmanager
def trace_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> Iterator[None]:
    """Record one read-only evidence query as an agento11y tool execution."""
    if _client is None:
        yield
        return
    with _client.start_tool_execution(
        ToolExecutionStart(tool_name=tool_name, tool_type="function", agent_name=AGENT_NAME)
    ) as rec:
        yield
        rec.set_result(ToolExecutionEnd(arguments=arguments))


def llm_run_config(node_name: str, conversation_id: str = "") -> dict[str, Any]:
    """LangChain RunnableConfig that records the LLM call made by `node_name`."""
    config: dict[str, Any] = {"run_name": node_name, "tags": [node_name]}
    if _client is None:
        return config
    return with_agento11y_langchain_callbacks(
        config,
        client=_client,
        agent_name=AGENT_NAME,
        provider="ollama",
        conversation_id=conversation_id,
        extra_tags={"node": node_name},
    )
