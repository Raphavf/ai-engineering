"""Builds and queries a FAISS vector store over the destinations knowledge base."""

import json

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings

EMBEDDING_MODEL = "models/embedding-001"


def load_documents(json_path: str = "data/destinations.json") -> list[Document]:
    """Load the destination entries and turn each one into a Document."""
    with open(json_path, encoding="utf-8") as f:
        entries = json.load(f)

    return [
        Document(page_content=entry["description"], metadata={"name": entry["name"]})
        for entry in entries
    ]


def build_index(json_path: str = "data/destinations.json") -> FAISS:
    """Embed all destination documents and build a FAISS index over them."""
    documents = load_documents(json_path)
    embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)
    return FAISS.from_documents(documents, embeddings)


def similarity_search(index: FAISS, query: str, k: int = 2) -> list[Document]:
    """Return the top-k most relevant destination documents for a query."""
    return index.similarity_search(query, k=k)
