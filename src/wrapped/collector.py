"""
Data collector — fetches all pages with metadata and content snippets.
No LLM calls — pure Notion API reads.
"""

import json
import asyncio

from src.mcp.client import NotionMCPClient


class WrappedCollector:

    def __init__(self, mcp_client: NotionMCPClient):
        self._mcp = mcp_client

    async def collect(self) -> list[dict]:
        """
        Discover all pages and collect metadata + content.
        Returns list of dicts: {id, title, created_time, last_edited_time, word_count, snippet}
        """
        pages = await self._discover_pages()
        print(f"\n[wrapped] Found {len(pages)} pages. Collecting content...")

        collected = []
        for i, page in enumerate(pages, 1):
            print(f"[wrapped] ({i}/{len(pages)}) Reading: {page['title']}")
            try:
                data = await self._collect_page(page)
                collected.append(data)
            except Exception as e:
                print(f"[wrapped] Error reading '{page['title']}': {e}")
                # Still include with empty content so stats aren't skewed
                collected.append({
                    "id": page["id"],
                    "title": page["title"],
                    "created_time": page.get("created_time", ""),
                    "last_edited_time": page.get("last_edited_time", ""),
                    "word_count": 0,
                    "snippet": "",
                })
            # Light rate limiting
            if i < len(pages):
                await asyncio.sleep(0.5)

        return collected

    async def _discover_pages(self) -> list[dict]:
        """Search for all pages accessible to the integration."""
        raw = await self._mcp.call_tool(
            "API-post-search",
            {
                "query": "",
                "filter": {"value": "page", "property": "object"},
                "page_size": 100,
            },
        )
        try:
            data = json.loads(raw)
        except Exception:
            return []

        pages = []
        for result in data.get("results", []):
            page_id = result.get("id", "")
            title = _extract_title(result)
            created_time = result.get("created_time", "")
            last_edited_time = result.get("last_edited_time", "")
            if page_id:
                pages.append({
                    "id": page_id,
                    "title": title,
                    "created_time": created_time,
                    "last_edited_time": last_edited_time,
                })
        return pages

    async def _collect_page(self, page: dict) -> dict:
        """Fetch block content for a single page."""
        blocks_raw = await self._mcp.call_tool(
            "API-get-block-children", {"block_id": page["id"]}
        )
        content = _extract_text_from_blocks(blocks_raw)
        words = content.split()
        word_count = len(words)
        # First 200 words for LLM snippet, first 50 for display
        snippet = " ".join(words[:200]) if words else ""

        return {
            "id": page["id"],
            "title": page["title"],
            "created_time": page["created_time"],
            "last_edited_time": page["last_edited_time"],
            "word_count": word_count,
            "snippet": snippet,
        }


def _extract_title(page: dict) -> str:
    try:
        props = page.get("properties", {})
        for prop in props.values():
            if prop.get("type") == "title":
                parts = prop.get("title", [])
                return "".join(p.get("plain_text", "") for p in parts)
    except Exception:
        pass
    return page.get("id", "Untitled")


def _extract_text_from_blocks(blocks_raw: str) -> str:
    try:
        data = json.loads(blocks_raw)
        results = data.get("results", [])
    except Exception:
        return ""

    lines = []
    for block in results:
        btype = block.get("type", "")
        content = block.get(btype, {})
        rich = content.get("rich_text", [])
        text = "".join(p.get("plain_text", "") for p in rich)
        if text:
            lines.append(text)
    return "\n".join(lines)
