"""
Heading-aware chunker.

For each Document:
  - Each (heading, body) section becomes the chunk candidate.
  - If the section fits in MAX_TOKENS, it becomes one chunk as-is.
  - If it's bigger, it gets split on paragraph boundaries with overlap,
    never crossing the H2 boundary (different sections never blend).

The result is a list of Chunks, each carrying its source metadata so we
can filter at retrieval time and cite back to the Notion page later.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import tiktoken

from loaders.base import Document


# --- settings (tune here later) -------------------------------------------------

TARGET_TOKENS = 350   # aim for chunks around this size when we have to split
MAX_TOKENS = 500      # if a section is at or below this, keep it as one chunk
OVERLAP_TOKENS = 50   # how much consecutive split-chunks share at the boundary

# cl100k_base is the tokenizer used by text-embedding-3-small (and GPT-4 family).
TOKENIZER = tiktoken.get_encoding("cl100k_base")


# --- output type ----------------------------------------------------------------


@dataclass
class Chunk:
    text: str
    metadata: dict = field(default_factory=dict)


# --- public API -----------------------------------------------------------------


def count_tokens(text: str) -> int:
    return len(TOKENIZER.encode(text))


def chunk_document(doc: Document) -> list[Chunk]:
    """Turn one Document into a list of Chunks."""
    chunks: list[Chunk] = []
    for section_index, (heading, body) in enumerate(doc.sections):
        body = body.strip()
        if not body:
            # Skip empty sections (e.g. an accidental duplicate H2 with no body).
            continue

        slices = _split_body(body)
        for slice_index, slice_text in enumerate(slices):
            full_text = f"## {heading}\n\n{slice_text}" if heading else slice_text
            chunks.append(
                Chunk(
                    text=full_text,
                    metadata={
                        "page_id": doc.page_id,
                        "title": doc.title,
                        "doc_type": doc.doc_type,
                        "entity": doc.entity,
                        "section_heading": heading,
                        "section_index": section_index,
                        "slice_index": slice_index,
                        "last_updated": doc.last_updated,
                    },
                )
            )
    return chunks


def chunk_documents(docs: list[Document]) -> list[Chunk]:
    out: list[Chunk] = []
    for doc in docs:
        out.extend(chunk_document(doc))
    return out


# --- internals ------------------------------------------------------------------


# Token budget reserved per chunk for the section heading we'll prepend later.
# Headings are usually short (~20 tokens) but we leave headroom.
_HEADING_HEADROOM = 50


def _split_body(body: str) -> list[str]:
    """Split a section body into chunk-sized slices.

    The H2 heading is NOT inside `body` here — chunk_document prepends it to
    each output slice. So we size against (MAX_TOKENS - heading_headroom) to
    keep the final chunk under MAX_TOKENS once the heading is added back.

    Strategy:
      1. If the body fits, return it whole (one slice).
      2. Otherwise split on paragraph breaks (\\n\\n).
      3. If any single paragraph is itself too big (e.g. a bullet list
         joined by single newlines), fall back to splitting on \\n.
      4. Group consecutive parts into slices that stay under TARGET_TOKENS,
         carrying ~OVERLAP_TOKENS from the tail of the previous slice.
    """
    effective_max = MAX_TOKENS - _HEADING_HEADROOM
    effective_target = TARGET_TOKENS - _HEADING_HEADROOM

    if count_tokens(body) <= effective_max:
        return [body]

    parts = [p.strip() for p in body.split("\n\n") if p.strip()]
    if not parts or any(count_tokens(p) > effective_max for p in parts):
        parts = [p.strip() for p in body.split("\n") if p.strip()]

    slices: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for p in parts:
        p_tokens = count_tokens(p)
        if current and current_tokens + p_tokens > effective_target:
            slices.append("\n".join(current))
            tail = current[-1]
            if count_tokens(tail) <= OVERLAP_TOKENS:
                current = [tail]
                current_tokens = count_tokens(tail)
            else:
                current = []
                current_tokens = 0
        current.append(p)
        current_tokens += p_tokens

    if current:
        slices.append("\n".join(current))

    return slices
