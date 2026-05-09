"""
Interactive retrieval test.

Type a question, see the top-K matching chunks from Pinecone with their
similarity scores. Lets you eyeball whether retrieval is finding the
right chunks before we hook up Claude in Phase 5.

    python -m uv run scripts/retrieve_test.py

Type 'exit' or Ctrl+C to quit.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)

from retriever import retrieve  # noqa: E402


SNIPPET_LEN = 220
DEFAULT_K = 5


def main() -> int:
    namespace = os.environ.get("PINECONE_NAMESPACE", "dev")
    k = DEFAULT_K

    print(f"Retrieval test — namespace={namespace!r}, k={k}.")
    print("Type a question and press Enter. 'exit' to quit.\n")

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

        results = retrieve(question, k=k, namespace=namespace)
        if not results:
            print("  (no results)\n")
            continue

        print(f"\nTop {len(results)} chunk(s):\n")
        for i, r in enumerate(results, 1):
            title = r.metadata.get("title", "?")
            section = r.metadata.get("section_heading", "?")
            doc_type = r.metadata.get("doc_type", "?")
            entity = r.metadata.get("entity", "?")
            snippet = r.text.replace("\n", " ").strip()
            if len(snippet) > SNIPPET_LEN:
                snippet = snippet[:SNIPPET_LEN] + "..."
            print(f"[{i}] score={r.score:.3f}  {doc_type}/{entity}  |  {title!r} > {section!r}")
            print(f"    {snippet}")
            print()


if __name__ == "__main__":
    sys.exit(main())
