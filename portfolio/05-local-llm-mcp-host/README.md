# Local LLM + MCP Host (Zero-Cost Setup)

A minimal Python **MCP host** that connects a locally-served, open-source LLM to the
`mcp-fiscal-reconciliation-server` (project 01) — no paid API calls anywhere in the loop.

This is the architecture I'd use to give non-technical staff natural-language access to the
reconciliation tool on company hardware, without sending fiscal data to any external API.

## Why "zero-cost"

- **Model**: an open-source, tool-calling-capable model (e.g. `qwen2.5` or `llama3.1`) served
  locally with [Ollama](https://ollama.com) — free, runs on a company server/workstation with a
  decent GPU, no per-token billing. Swapping in a self-hosted Hugging Face model (via
  `transformers` + `text-generation-inference`, or the free-tier Hugging Face Inference API for
  testing) works the same way — see the note at the bottom.
- **Host**: this repo's `host.py` — a plain Python script, no framework license, no hosted agent
  platform.
- **Tools**: the MCP server from project 01, running as a local subprocess (stdio transport) —
  same machine, same network, no cloud dependency.

```
User (CLI)
    │
    ▼
host.py  ──spawns──▶  server.py (project 01, MCP tools over stdio)
    │
    ▼
Local LLM (Ollama, running on a company server/GPU box)
```

## How the loop works

1. The user types a question.
2. `host.py` sends the question (plus the list of available MCP tools) to the local model.
3. If the model decides a tool is needed, `host.py` calls that tool on the MCP server and sends
   the result back to the model.
4. The model either asks for another tool call or gives a final answer.
5. Repeat until the model responds with plain text instead of a tool call.

This is the same "agentic loop" pattern used by hosted assistants — the difference here is that
every piece of it (model, host, tools) runs on infrastructure the company already owns or controls.

## Running it

```bash
pip install -r requirements.txt

# 1. Install Ollama and pull a tool-calling capable model:
#    https://ollama.com/download
ollama pull qwen2.5:7b

# 2. Point this host at project 01's server, then run:
python host.py --server ../01-mcp-fiscal-reconciliation-server/server.py
```

## Swapping in a Hugging Face model instead of Ollama

`host.py` only talks to the model through the small `call_local_llm()` function in `llm_client.py`.
To use Hugging Face instead of Ollama (e.g. a model served with `text-generation-inference` on a
company GPU box, or the free Hugging Face Inference API for a quick test), replace the body of that
one function with a call to `huggingface_hub.InferenceClient` — nothing else in `host.py` needs to
change, since the rest of the loop only depends on the `(tool_calls, text)` shape it returns.
