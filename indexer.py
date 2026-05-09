"""
Indexer — embed chunks via OpenAI and upsert them to Pinecone.

Library code. Called by scripts/index_run.py (or any future script that
needs to write content into Pinecone).

Functions:
  embed_chunks(chunks)                -> list of vectors
  upsert_chunks(chunks, vectors, ns)  -> upsert vector records into Pinecone
  partition_by_change(chunks, ns)     -> (unchanged, changed) — incremental skip
  reconcile(current_ids, ns)          -> delete vectors not in current_ids
  content_hash(text)                  -> sha256 fingerprint of a chunk's text
"""

from __future__ import annotations

import hashlib
import os
from typing import Any

from openai import OpenAI
from pinecone import Pinecone

from chunker import Chunk


EMBED_MODEL = os.environ.get("OPENAI_EMBED_MODEL", "text-embedding-3-small")
UPSERT_BATCH_SIZE = 100   # Pinecone allows up to ~1000; 100 is comfortable
FETCH_BATCH_SIZE = 100    # Pinecone fetch limit per call
DELETE_BATCH_SIZE = 1000  # Pinecone delete limit per call


def _index():
    """Internal helper — open a Pinecone index handle from env config."""
    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    return pc.Index(os.environ["PINECONE_INDEX_NAME"])


# ----------------------------------------------------------------- ID generation


def chunk_to_id(chunk: Chunk) -> str:
    """Stable ID for a chunk so re-runs upsert in place rather than duplicate.

    Format: <notion-page-id>:<section-index>:<slice-index>
    """
    m = chunk.metadata
    return f"{m['page_id']}:{m['section_index']}:{m['slice_index']}"


def content_hash(text: str) -> str:
    """sha256 fingerprint of a chunk's text. Stored in Pinecone metadata so
    next runs can detect "this chunk is unchanged" without re-embedding."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ----------------------------------------------------------------- embedding


def embed_chunks(chunks: list[Chunk]) -> list[list[float]]:
    """Embed every chunk's text via OpenAI. Returns one vector per chunk, in order."""
    if not chunks:
        return []
    client = OpenAI()  # picks up OPENAI_API_KEY from env automatically
    resp = client.embeddings.create(
        model=EMBED_MODEL,
        input=[c.text for c in chunks],
    )
    return [d.embedding for d in resp.data]


# ----------------------------------------------------------------- upserting


def upsert_chunks(
    chunks: list[Chunk],
    vectors: list[list[float]],
    namespace: str = "dev",
) -> int:
    """Upsert chunks (with their pre-computed embeddings) to Pinecone.

    Returns the number of records upserted.
    """
    if not chunks:
        return 0
    if len(chunks) != len(vectors):
        raise ValueError(
            f"chunks and vectors length mismatch: {len(chunks)} vs {len(vectors)}"
        )

    index = _index()

    records: list[dict[str, Any]] = []
    for chunk, vec in zip(chunks, vectors):
        records.append(
            {
                "id": chunk_to_id(chunk),
                "values": vec,
                "metadata": _metadata_for_pinecone(chunk),
            }
        )

    for i in range(0, len(records), UPSERT_BATCH_SIZE):
        batch = records[i : i + UPSERT_BATCH_SIZE]
        index.upsert(vectors=batch, namespace=namespace)

    return len(records)


# --------------------------------------------------------- incremental & cleanup


def partition_by_change(
    chunks: list[Chunk],
    namespace: str = "dev",
) -> tuple[list[Chunk], list[Chunk]]:
    """Compare each chunk's hash against what's already in Pinecone.

    Returns (unchanged, changed). 'changed' includes brand-new chunks (no
    existing record at that ID) and modified ones (hash differs from stored).
    """
    if not chunks:
        return [], []

    index = _index()
    chunk_by_id = {chunk_to_id(c): c for c in chunks}
    ids = list(chunk_by_id.keys())

    fetched: dict[str, Any] = {}
    for i in range(0, len(ids), FETCH_BATCH_SIZE):
        batch = ids[i : i + FETCH_BATCH_SIZE]
        resp = index.fetch(ids=batch, namespace=namespace)
        # resp.vectors is a dict-like mapping id -> Vector record
        vectors = getattr(resp, "vectors", None) or resp.get("vectors", {})
        for k, v in vectors.items():
            fetched[k] = v

    unchanged: list[Chunk] = []
    changed: list[Chunk] = []
    for cid, chunk in chunk_by_id.items():
        existing = fetched.get(cid)
        new_hash = content_hash(chunk.text)
        existing_hash = _read_metadata_field(existing, "content_hash") if existing else None
        if existing_hash == new_hash:
            unchanged.append(chunk)
        else:
            changed.append(chunk)
    return unchanged, changed


def reconcile(current_ids: set[str], namespace: str = "dev") -> int:
    """Delete vectors in the namespace whose IDs are NOT in current_ids.

    Use after upserting to remove orphans (chunks from pages now Drafted /
    deleted / removed from the corpus). Returns count of orphans deleted.
    """
    index = _index()

    all_ids: list[str] = []
    for batch in index.list(namespace=namespace):
        for item in batch:
            # Pinecone may yield bare strings or ListItem-like objects with .id
            if isinstance(item, str):
                all_ids.append(item)
            else:
                all_ids.append(getattr(item, "id", str(item)))

    orphans = [i for i in all_ids if i not in current_ids]
    if not orphans:
        return 0

    for i in range(0, len(orphans), DELETE_BATCH_SIZE):
        index.delete(ids=orphans[i : i + DELETE_BATCH_SIZE], namespace=namespace)
    return len(orphans)


def _read_metadata_field(record: Any, key: str) -> str | None:
    """Read a metadata field from a Pinecone record, handling dict and object shapes."""
    if record is None:
        return None
    metadata = getattr(record, "metadata", None)
    if metadata is None and isinstance(record, dict):
        metadata = record.get("metadata")
    if not metadata:
        return None
    if isinstance(metadata, dict):
        return metadata.get(key)
    return getattr(metadata, key, None)


# ----------------------------------------------------------------- helpers


def _metadata_for_pinecone(chunk: Chunk) -> dict[str, Any]:
    """Build the metadata dict stored alongside the vector in Pinecone.

    Includes:
      - source-identifying fields (title, doc_type, entity, section_heading)
      - the chunk's text so we can read it back at retrieval time (Phase 4)
        without keeping a separate database of chunk texts
      - a content_hash so the next index run can detect "this chunk is
        unchanged" and skip re-embedding
    """
    m = chunk.metadata
    return {
        "title": m.get("title", ""),
        "doc_type": m.get("doc_type", ""),
        "entity": m.get("entity", ""),
        "section_heading": m.get("section_heading", ""),
        "last_updated": m.get("last_updated", ""),
        "content_hash": content_hash(chunk.text),
        "text": chunk.text,
    }
