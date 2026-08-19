# Travel Recommendation Chatbot (RAG)

A retrieval-augmented chatbot that recommends travel destinations based on a small knowledge base of
destination descriptions. Built as a coursework project to get hands-on with the RAG stack: chunking
and embedding text, storing it in a vector database, retrieving relevant context at query time, and
feeding that context to an LLM (Google Gemini) instead of relying on the model's own memory.

## How it works

```
destinations.json  (raw text descriptions)
        │  chunk + embed
        ▼
   FAISS vector store
        │  similarity search on the user's question
        ▼
   top-k relevant chunks
        │  injected into the prompt as context
        ▼
   Gemini generates the answer
```

## Structure

- `data/destinations.json` — small sample knowledge base of destination descriptions
- `vector_store.py` — builds and queries the FAISS vector store
- `chatbot.py` — the RAG chain: retrieve context, then ask Gemini
- `main.py` — simple CLI loop to chat with it

## Running it

```bash
pip install -r requirements.txt
export GOOGLE_API_KEY=your-key-here
python main.py
```

## Why FAISS

FAISS runs in-process with no external service to stand up, which made it the right choice for a
course project meant to focus on the RAG concepts themselves rather than infra setup. The same
`vector_store.py` interface (`build_index` / `similarity_search`) would swap cleanly for a hosted store
like Pinecone or Weaviate if this needed to scale past a local knowledge base.
