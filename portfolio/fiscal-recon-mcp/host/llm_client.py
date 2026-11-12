"""
host/llm_client.py

Thin wrapper around a locally served LLM (Ollama by default). Swapping
the backend only means rewriting `call_local_llm`; host.py doesn't change.
"""

from __future__ import annotations

import os

import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL_NAME = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")  # any model with tool calling


def call_local_llm(messages: list[dict], tools: list[dict]) -> dict:
    """Send the conversation and tools; returns Ollama's assistant message
    (either `content` or `tool_calls`)."""
    response = requests.post(
        OLLAMA_URL,
        json={"model": MODEL_NAME, "messages": messages, "tools": tools, "stream": False},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["message"]
