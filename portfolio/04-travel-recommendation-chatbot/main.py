"""Simple CLI loop to chat with the travel recommendation bot."""

from chatbot import ask
from vector_store import build_index

if __name__ == "__main__":
    print("Building the destination index...")
    index = build_index()
    print("Ready. Ask about a trip (Ctrl+C to quit).\n")

    while True:
        question = input("You: ")
        answer = ask(index, question)
        print(f"\nBot: {answer}\n")
