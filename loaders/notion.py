"""
NotionLoader — fetches Ready pages from a Notion database and returns Documents.

Each page becomes one Document, with body blocks grouped into (H2 heading, body)
sections so the chunker downstream can split cleanly along those boundaries.
"""

from __future__ import annotations

import os

from notion_client import Client

from .base import Document, Loader


class NotionLoader(Loader):
    """Loads pages from the Notion database the integration has access to."""

    def __init__(self, api_key: str | None = None):
        self.client = Client(auth=api_key or os.environ["NOTION_API_KEY"])

    # ------------------------------------------------------------------ public

    def load(self) -> list[Document]:
        """Fetch all accessible pages, return one Document per Ready page."""
        results = self.client.search().get("results", [])
        pages = [r for r in results if r.get("object") == "page"]

        documents: list[Document] = []
        for page in pages:
            doc = self._page_to_document(page)
            if doc is not None:
                documents.append(doc)
        return documents

    # ------------------------------------------------------------------ internals

    def _page_to_document(self, page: dict) -> Document | None:
        """Convert a Notion page to a Document. Returns None if Status != Ready."""
        props = page["properties"]

        status = self._read_select_or_text(props.get("Status"))
        if status != "Ready":
            return None

        title = self._read_title(props.get("Name"))
        doc_type = self._read_select_or_text(props.get("Doc Type")) or "Unknown"
        entity = self._read_select_or_text(props.get("Entity")) or "Unknown"
        last_updated = page.get("last_edited_time", "")

        sections = self._read_sections(page["id"])

        return Document(
            page_id=page["id"],
            title=title,
            doc_type=doc_type,
            entity=entity,
            last_updated=last_updated,
            sections=sections,
        )

    # -------- property readers (Notion's API has different shapes per type)

    @staticmethod
    def _read_title(prop: dict | None) -> str:
        if not prop or prop.get("type") != "title":
            return ""
        return "".join(t.get("plain_text", "") for t in prop.get("title", []))

    @staticmethod
    def _read_select_or_text(prop: dict | None) -> str:
        """Return the value whether the property is a Select or a plain Text field."""
        if not prop:
            return ""
        ptype = prop.get("type")
        if ptype == "select":
            sel = prop.get("select") or {}
            return sel.get("name", "")
        if ptype == "rich_text":
            return "".join(t.get("plain_text", "") for t in prop.get("rich_text", []))
        return ""

    # -------- block reading and section grouping

    def _read_sections(self, page_id: str) -> list[tuple[str, str]]:
        """Read every block on the page, group into (h2, body) sections."""
        blocks = self._all_blocks(page_id)

        sections: list[tuple[str, str]] = []
        current_heading = ""
        current_body: list[str] = []

        for block in blocks:
            btype = block["type"]
            if btype == "heading_2":
                # Close previous section
                if current_body or current_heading:
                    sections.append((current_heading, "\n".join(current_body).strip()))
                current_heading = self._block_text(block)
                current_body = []
            else:
                line = self._block_text(block)
                if line:
                    current_body.append(line)

        # Close the final section
        if current_body or current_heading:
            sections.append((current_heading, "\n".join(current_body).strip()))

        return sections

    def _all_blocks(self, page_id: str) -> list[dict]:
        """Page through all blocks of a page (handles >100 blocks via pagination)."""
        out: list[dict] = []
        cursor: str | None = None
        while True:
            kwargs: dict = {"block_id": page_id, "page_size": 100}
            if cursor:
                kwargs["start_cursor"] = cursor
            resp = self.client.blocks.children.list(**kwargs)
            out.extend(resp.get("results", []))
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
        return out

    @staticmethod
    def _block_text(block: dict) -> str:
        """Render one block as plain text. Preserves enough markdown for the chunker."""
        btype = block["type"]
        payload = block.get(btype, {})
        rich = payload.get("rich_text", [])
        text = "".join(t.get("plain_text", "") for t in rich)

        if btype in ("bulleted_list_item", "numbered_list_item"):
            return f"- {text}"
        if btype == "heading_3":
            return f"### {text}"
        if btype == "heading_1":
            return f"# {text}"
        if btype == "quote":
            return f"> {text}"
        if btype == "code":
            language = payload.get("language", "")
            return f"```{language}\n{text}\n```"
        if btype == "divider":
            return ""
        # paragraph and anything else: just the text
        return text
