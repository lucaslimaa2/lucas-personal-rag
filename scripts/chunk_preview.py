"""
Phase 2 preview: load Notion pages, chunk them, print the result.

Run with:
    python -m uv run scripts/chunk_preview.py
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

# Make project root importable so `loaders` and `chunker` resolve.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)

from loaders.notion import NotionLoader  # noqa: E402
from chunker import chunk_documents, count_tokens  # noqa: E402


def main() -> int:
    print("Loading documents from Notion...")
    loader = NotionLoader()
    docs = loader.load()
    print(f"  Loaded {len(docs)} document(s):")
    for d in docs:
        print(f"    - {d.title!r}  type={d.doc_type}  entity={d.entity}  sections={len(d.sections)}")
    print()

    print("Chunking...")
    chunks = chunk_documents(docs)
    print(f"  Produced {len(chunks)} chunk(s).")
    print()

    print("=" * 70)
    print("CHUNK PREVIEW")
    print("=" * 70)
    for i, c in enumerate(chunks):
        m = c.metadata
        tokens = count_tokens(c.text)
        header = f"Chunk {i + 1}/{len(chunks)} | {tokens} tokens | {m['title']!r} > {m['section_heading']!r}"
        print()
        print("-" * 70)
        print(header)
        print("-" * 70)
        snippet = c.text if len(c.text) <= 600 else c.text[:600] + "..."
        print(snippet)

    return 0


if __name__ == "__main__":
    sys.exit(main())
