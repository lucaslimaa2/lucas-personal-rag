"""
End-to-end indexer with incremental skip + orphan reconciliation.

Run any time Notion content changes. Re-runs only embed chunks whose text
actually changed, and Pinecone is reconciled so deleted/Drafted pages
disappear from the index.

    python -m uv run scripts/index_run.py

Default Pinecone namespace is "dev". Override with:
    PINECONE_NAMESPACE=prod python -m uv run scripts/index_run.py
"""

from __future__ import annotations

import os
import sys
import time

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)

from loaders.notion import NotionLoader  # noqa: E402
from chunker import chunk_documents, count_tokens  # noqa: E402
from indexer import (  # noqa: E402
    chunk_to_id,
    embed_chunks,
    partition_by_change,
    reconcile,
    upsert_chunks,
)


def main() -> int:
    namespace = os.environ.get("PINECONE_NAMESPACE", "dev")

    print("[1/5] Loading documents from Notion...")
    docs = NotionLoader().load()
    print(f"      {len(docs)} document(s) loaded.")
    if not docs:
        print("      Nothing to index. Make sure pages are marked Status = Ready.")
        # Still reconcile so previously-indexed (now Drafted) pages are removed.
        deleted = reconcile(set(), namespace=namespace)
        print(f"      Reconcile deleted {deleted} orphan(s).")
        return 0

    print("[2/5] Chunking...")
    chunks = chunk_documents(docs)
    total_tokens = sum(count_tokens(c.text) for c in chunks)
    print(f"      {len(chunks)} chunk(s), {total_tokens} total tokens.")

    print(f"[3/5] Checking what's changed in Pinecone (namespace={namespace!r})...")
    unchanged, to_embed = partition_by_change(chunks, namespace=namespace)
    print(f"      {len(unchanged)} chunk(s) unchanged (skipping)")
    print(f"      {len(to_embed)} chunk(s) new or modified")

    if to_embed:
        print(f"[4/5] Embedding {len(to_embed)} chunk(s) via OpenAI...")
        t0 = time.time()
        vectors = embed_chunks(to_embed)
        print(f"      Done in {time.time() - t0:.2f}s.")

        print(f"[5/5] Upserting {len(to_embed)} + reconciling orphans...")
        n = upsert_chunks(to_embed, vectors, namespace=namespace)
        print(f"      Upserted {n}.")
    else:
        print("[4/5] No embedding needed.")
        print("[5/5] Reconciling orphans only...")

    current_ids = {chunk_to_id(c) for c in chunks}
    orphan_count = reconcile(current_ids, namespace=namespace)
    print(f"      Deleted {orphan_count} orphan(s).")

    print()
    print(f"Indexing complete. Pinecone namespace {namespace!r} is up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
