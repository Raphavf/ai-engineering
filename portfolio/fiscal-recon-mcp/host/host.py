"""
host/host.py

Minimal MCP host: starts the fiscal-recon MCP server over stdio, lists
its tools, and runs an agentic loop against a local LLM (Ollama). No
hosted agent framework, no paid API.

    python host/host.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from llm_client import call_local_llm

SYSTEM_PROMPT = (
    "You are an assistant with access to fiscal reconciliation tools. "
    "Use them when the user asks about reconciliation status, divergent "
    "records, or a specific record. Otherwise answer directly."
)

# Stop runaway loops where a small model keeps calling tools forever
MAX_TOOL_ROUNDS = 8


def mcp_tools_to_ollama(mcp_tools) -> list[dict]:
    """Convert the MCP tool list into Ollama's tool-calling schema."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema,
            },
        }
        for tool in mcp_tools
    ]


def tool_result_to_text(result) -> str:
    """Flatten MCP content blocks into plain text the model can read."""
    parts = [getattr(block, "text", None) or str(block) for block in result.content]
    text = "\n".join(parts)
    return f"ERROR: {text}" if getattr(result, "isError", False) else text


def parse_arguments(raw) -> dict:
    """Some models return arguments as a JSON string instead of an object."""
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw or {}


async def answer(session: ClientSession, messages: list[dict], tools: list[dict]) -> str:
    for _ in range(MAX_TOOL_ROUNDS):
        assistant_message = call_local_llm(messages, tools)
        messages.append(assistant_message)

        tool_calls = assistant_message.get("tool_calls")
        if not tool_calls:
            return assistant_message.get("content", "")

        for call in tool_calls:
            name = call["function"]["name"]
            args = parse_arguments(call["function"].get("arguments"))
            print(f"  [tool] {name}({args})")
            result = await session.call_tool(name, args)
            messages.append({"role": "tool", "content": tool_result_to_text(result)})

    return "(stopped: too many tool calls in a row)"


async def run_chat_loop(server_command: list[str]) -> None:
    params = StdioServerParameters(command=server_command[0], args=server_command[1:])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = mcp_tools_to_ollama((await session.list_tools()).tools)
            print(f"Connected. {len(tools)} tool(s) available. Type 'exit' to quit.\n")

            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            while True:
                user_input = input("You: ")
                if user_input.strip().lower() in ("exit", "quit"):
                    break
                messages.append({"role": "user", "content": user_input})
                print(f"\nBot: {await answer(session, messages, tools)}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MCP host backed by a local LLM.")
    parser.add_argument(
        "--server",
        nargs="+",
        default=[sys.executable, "-m", "fiscal_recon.mcp_server"],
        help="command that starts the MCP server",
    )
    asyncio.run(run_chat_loop(parser.parse_args().server))
