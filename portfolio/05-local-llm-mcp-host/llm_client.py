"""
llm_client.py

Thin wrapper around a locally-served LLM (Ollama by default). Isolated
in its own function so swapping the backend (e.g. to Hugging Face
Inference) only means rewriting `call_local_llm` -- host.py doesn't
change.
"""

import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5:7b"  # any Ollama model with tool-calling support


def call_local_llm(messages: list[dict], tools: list[dict]) -> dict:
    """Send the conversation + available tools to the local model.

    Returns the raw assistant message dict from Ollama, which may
    contain either a `content` string or a `tool_calls` list.
    """
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL_NAME,
            "messages": messages,
            "tools": tools,
            "stream": False,
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["message"]
