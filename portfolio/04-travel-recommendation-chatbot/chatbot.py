"""The RAG chain: retrieve relevant destinations, then ask Gemini to answer using them."""

from langchain_google_genai import ChatGoogleGenerativeAI

from vector_store import similarity_search

CHAT_MODEL = "gemini-1.5-flash"

SYSTEM_PROMPT = (
    "You are a travel recommendation assistant. Use only the destination "
    "information provided below to answer the user's question. If none of "
    "the destinations fit, say so honestly instead of inventing one.\n\n"
    "Destinations:\n{context}"
)


def ask(index, question: str) -> str:
    """Retrieve relevant destinations and generate a grounded answer."""
    relevant_docs = similarity_search(index, question)
    context = "\n\n".join(f"{doc.metadata['name']}: {doc.page_content}" for doc in relevant_docs)

    llm = ChatGoogleGenerativeAI(model=CHAT_MODEL)
    prompt = SYSTEM_PROMPT.format(context=context) + f"\n\nQuestion: {question}"

    response = llm.invoke(prompt)
    return response.content
