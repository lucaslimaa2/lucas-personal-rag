"""
Lucas Resume + VEGA chatbot — CLI.

Multi-turn conversation. Type a question, get a grounded answer pulled
from the Notion-backed knowledge base in Pinecone.

    python -m uv run scripts/chat_cli.py

Commands inside the REPL:
  exit / quit  - leave
  reset        - clear conversation history
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)

from chat import answer  # noqa: E402


def main() -> int:
    namespace = os.environ.get("PINECONE_NAMESPACE", "dev")
    history: list[dict] = []

    print(f"Lucas RAG chatbot — namespace={namespace!r}.")
    print("Type a question. 'exit' to quit. 'reset' to clear conversation history.")
    print()

    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not question:
            continue
        if question.lower() in {"exit", "quit"}:
            return 0
        if question.lower() == "reset":
            history = []
            print("(history cleared)\n")
            continue

        try:
            assistant_text, history, _results = answer(
                question, history=history, namespace=namespace
            )
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}\n")
            continue

        print()
        print(assistant_text)
        print()


if __name__ == "__main__":
    sys.exit(main())
