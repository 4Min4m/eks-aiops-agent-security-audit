"""Thin wrapper around the local Ollama model.

Design choice: a local model (Ollama), no paid API key. This means the
agento11y instrumentation has no $-cost dimension to show — only
generations and latency apply here, and that's stated plainly rather than
glossed over.
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
