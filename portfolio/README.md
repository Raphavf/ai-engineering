# AI Engineering & AI Automation Portfolio

**Raphael Muniz** — Data Engineer (6+ years) transitioning into AI Engineering / AI Automation.
Background: multi-ERP reconciliation systems (SAP B1/HANA, TOTVS RMS, Oracle PL/SQL) across 20+ retail
branch locations, now extending that domain expertise into LLM tool-calling architectures using the
Model Context Protocol (MCP).

> **Note on the code in this portfolio:** these projects are built from real production patterns I
> use at work, but all company names, schemas, table names, and business-specific field names have
> been **genericized/anonymized** for public sharing. The architecture, the bugs I hit, and the
> reasoning behind each design decision are real.

## Projects

### 1. [`mcp-fiscal-reconciliation-server`](./01-mcp-fiscal-reconciliation-server)
An MCP (Model Context Protocol) server that exposes a fiscal/financial reconciliation pipeline as
tools an LLM agent can call. This is the anchor project for my AI Engineering specialization: it takes
a real, already-working pandas-based reconciliation script and wraps it safely for agentic use —
solving problems that don't show up in tutorials, like DataFrame → JSON serialization, caching to
avoid hammering production databases during multi-step agent loops, and pseudonymizing sensitive data
before it reaches an LLM.

**Concepts demonstrated:** MCP tool primitives, in-memory TTL caching, safe serialization of
`pandas`/`numpy` types, HMAC-based data pseudonymization, Fernet-encrypted credential storage.

### 2. [`fiscal-reconciliation-api`](./02-fiscal-reconciliation-api)
The underlying reconciliation service as a standalone, testable Python package — the same logic the
MCP server calls into, but structured as a proper `src/` layout project with Pydantic v2 models,
connection-pooled database connectors, a FastAPI layer, and a pytest suite. This is the "boring but
correct" foundation the AI-facing layer depends on.

**Concepts demonstrated:** `src/` package layout, Pydantic v2 validation & computed properties,
connection pooling, business-rule validation (date-window enforcement), unit testing with mocked
database connectors.

### 3. [`tiktok-video-analyzer`](./03-tiktok-video-analyzer)
A pipeline that downloads a TikTok video, extracts key frames, and uses Claude Vision to analyze
hook, lighting, camera angle, and selling points per frame — then consolidates everything into a
client-ready report. Built in a few days going from zero Claude API experience to a working
end-to-end multimodal pipeline, including real debugging (Windows encoding issues, yt-dlp quirks,
TikTok download blocking).

**Concepts demonstrated:** Claude Vision (multimodal) API calls, a simple multi-stage pipeline
(download → extract → analyze → summarize), practical cross-platform debugging.

### 4. [`travel-recommendation-chatbot`](./04-travel-recommendation-chatbot)
A retrieval-augmented (RAG) chatbot recommending travel destinations from a small knowledge base.
Built as a coursework project to get hands-on with the full RAG stack: chunking, embeddings, a FAISS
vector store, similarity search, and grounding an LLM's (Google Gemini) answer in retrieved context
instead of its own memory.

**Concepts demonstrated:** RAG architecture, embeddings, vector similarity search with FAISS,
LangChain, prompting an LLM to answer only from retrieved context.

### 5. [`local-llm-mcp-host`](./05-local-llm-mcp-host)
A zero-cost variant of project 1's architecture: instead of a hosted assistant (Claude Desktop, etc.)
acting as the MCP host, this is a small Python script that plays that role itself, talking to an
open-source model served locally (Ollama, or a self-hosted Hugging Face model) instead of a paid API.
This is the architecture I'd use to expose the reconciliation tools internally without sending fiscal
data outside company infrastructure.

**Concepts demonstrated:** writing an MCP *host* (not just a server) from scratch, the tool-calling
agentic loop end to end, running entirely on self-hosted/open-source infrastructure.

## A recurring theme across these projects

**The AI layer is only as trustworthy as the data layer underneath it.** Before I let an LLM call a
tool (projects 1 and 2), that tool needs to already be correct, tested, and safe to call repeatedly —
caching, timeouts, and read-only guarantees aren't "nice to haves" once an autonomous agent is the one
deciding when to call your code. Projects 3 and 4 show the other side: getting hands-on with the core
building blocks (multimodal calls, RAG, vector search) that make an AI system useful in the first
place.

## About me

- Data Engineer at a multi-branch retail company, reconciling fiscal data across SAP B1/HANA, TOTVS
  RMS, and Oracle.
- Postgraduate specialization in AI Engineering (Instituto Infnet).
- Hands-on with LangChain, LangGraph, LangSmith, RAG/embeddings, MCP tool-calling, and the Anthropic
  API.
- Actively looking for remote AI Engineering / AI Automation roles.
- [LinkedIn](https://www.linkedin.com/in/raphael-muniz-pacheco-41061677/) · [Email](r.munizpacheco@hotmail.com) .[GitHub](https://github.com/Raphavf)
