"""
Retriever — embed a question and search Pinecone for the K most relevant chunks.

Library code. Used by:
  - scripts/retrieve_test.py (manual eyeballing)
  - Phase 5's chatbot (will call retrieve() before asking Claude)

Critical rule: we embed the question with the SAME model used for the chunks
in Phase 3 (text-embedding-3-small). Mismatched models → vectors live in
different "semantic spaces" → similarity search returns garbage.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI
from pinecone import Pinecone


EMBED_MODEL = os.environ.get("OPENAI_EMBED_MODEL", "text-embedding-3-small")
DEFAULT_K = 10


@dataclass
class RetrievalResult:
    """One chunk returned by retrieval, with its similarity score and metadata."""
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------- public API


def embed_query(question: str) -> list[float]:
    """Embed a single question. MUST use the same model as chunks were embedded with."""
    client = OpenAI()  # picks up OPENAI_API_KEY from env
    resp = client.embeddings.create(
        model=EMBED_MODEL,
        input=[question],
    )
    return resp.data[0].embedding


def retrieve(
    question: str,
    k: int = DEFAULT_K,
    namespace: str = "dev",
    filter: dict[str, Any] | None = None,
) -> list[RetrievalResult]:
    """Return the top-K chunks most relevant to a question, ordered by score (high first).

    Args:
      question:  the user's question (a string).
      k:         how many chunks to return.
      namespace: Pinecone namespace to search ("dev" / "prod").
      filter:    optional Pinecone metadata filter, e.g. {"doc_type": {"$eq": "Resume"}}.

    Returns:
      list[RetrievalResult]. Empty if the question is blank.
    """
    if not question.strip():
        return []

    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    index = pc.Index(os.environ["PINECONE_INDEX_NAME"])

    query_vector = embed_query(question)

    kwargs: dict[str, Any] = {
        "vector": query_vector,
        "top_k": k,
        "namespace": namespace,
        "include_metadata": True,
    }
    if filter:
        kwargs["filter"] = filter

    resp = index.query(**kwargs)
    matches = _matches_from_response(resp)

    results: list[RetrievalResult] = []
    for m in matches:
        meta = _read_metadata(m)
        results.append(
            RetrievalResult(
                text=meta.get("text", ""),
                score=_read_score(m),
                metadata=meta,
            )
        )
    return results


# --------------------------------------------------------------- helpers


def _matches_from_response(resp: Any) -> list[Any]:
    """Pinecone returns either a dict-like object or a Pydantic model. Handle both."""
    if isinstance(resp, dict):
        return resp.get("matches", []) or []
    return getattr(resp, "matches", []) or []


def _read_score(match: Any) -> float:
    if isinstance(match, dict):
        return float(match.get("score", 0.0))
    return float(getattr(match, "score", 0.0))


def _read_metadata(match: Any) -> dict[str, Any]:
    if isinstance(match, dict):
        return match.get("metadata") or {}
    metadata = getattr(match, "metadata", None)
    if metadata is None:
        return {}
    if isinstance(metadata, dict):
        return metadata
    # Pydantic model — coerce to dict
    return {k: getattr(metadata, k, None) for k in dir(metadata) if not k.startswith("_")}
