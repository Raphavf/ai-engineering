"""
host.py

A minimal MCP host: connects to an MCP server (project 01) over stdio,
lists its tools, and runs an agentic loop against a local LLM (see
llm_client.py). No hosted agent framework, no paid API.
"""

import argparse
import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from llm_client import call_local_llm

SYSTEM_PROMPT = (
    "You are an assistant with access to fiscal reconciliation tools. "
    "Use them when the user asks about reconciliation status, divergent "
    "records, or a specific record. Otherwise answer directly."
)


def _mcp_tools_to_ollama_format(mcp_tools) -> list[dict]:
    """Convert the MCP tool list into the schema Ollama expects for tool-calling."""
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


async def run_chat_loop(server_script_path: str):
    server_params = StdioServerParameters(command="python", args=[server_script_path])

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_response = await session.list_tools()
            ollama_tools = _mcp_tools_to_ollama_format(tools_response.tools)
            print(f"Connected. {len(ollama_tools)} tool(s) available.\n")

            messages = [{"role": "system", "content": SYSTEM_PROMPT}]

            while True:
                user_input = input("You: ")
                if user_input.strip().lower() in ("exit", "quit"):
                    break

                messages.append({"role": "user", "content": user_input})

                # Keep calling the model until it responds without a tool call
                while True:
                    assistant_message = call_local_llm(messages, ollama_tools)
                    messages.append(assistant_message)

                    tool_calls = assistant_message.get("tool_calls")
                    if not tool_calls:
                        print(f"\nBot: {assistant_message.get('content', '')}\n")
                        break

                    for call in tool_calls:
                        name = call["function"]["name"]
                        args = call["function"]["arguments"]
                        result = await session.call_tool(name, args)
                        messages.append(
                            {
                                "role": "tool",
                                "content": str(result.content),
                            }
                        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MCP host backed by a local LLM.")
    parser.add_argument("--server", required=True, help="Path to the MCP server script (server.py)")
    args = parser.parse_args()

    asyncio.run(run_chat_loop(args.server))
