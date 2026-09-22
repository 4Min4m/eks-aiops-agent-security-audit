"""Thin wrapper around the local Ollama model.

Chosen per Amin's call: local model (Ollama), no paid API key. This means
Phase 3's agento11y instrumentation won't have a $-cost dimension to show —
that's worth stating plainly in the demo/README rather than glossing over,
since "cost tracking" is one of the three things agento11y advertises
(generations, latency, cost) and only two of the three apply here.
"""
from __future__ import annotations

import os

from langchain_ollama import ChatOllama

_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


def get_llm(temperature: float = 0.1) -> ChatOllama:
    """Return a configured ChatOllama client.

    temperature is kept low (0.1) on purpose: this agent produces an
    incident summary someone will act on, not creative text. Consistency
    across runs matters more than variety here.
    """
    return ChatOllama(model=_MODEL, base_url=_BASE_URL, temperature=temperature)
