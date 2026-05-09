"""
Loader interface and Document type.

A Loader fetches content from some source (Notion, Confluence, Drive, ...)
and returns a list of Documents. The chunker downstream takes any Loader's
output without caring which source it came from.

To add a new source later, write a new class that inherits from Loader and
implements load(). Nothing else in the pipeline changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Document:
    """One source document, ready to be chunked.

    sections is a list of (heading, body_text) tuples — one per H2 in the page.
    Blocks before the first H2 (if any) live under heading="".
    """

    page_id: str
    title: str
    doc_type: str
    entity: str
    last_updated: str
    sections: list[tuple[str, str]] = field(default_factory=list)


class Loader:
    """Base class. Every loader must implement load() returning a list[Document]."""

    def load(self) -> list[Document]:
        raise NotImplementedError
