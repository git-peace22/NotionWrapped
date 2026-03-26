"""
Workspace organizer — discovers all accessible pages and runs the
organization agent on each unprocessed one.
"""

import asyncio
import json

from src.mcp.client import NotionMCPClient
from src.agent.core import OrganizationAgent
from src.config import settings

ALREADY_PROCESSED_MARKER = "🧠 Second Brain Index"


class WorkspaceOrganizer:

    def __init__(self, mcp_client: NotionMCPClient):
        self._mcp = mcp_client
        self._agent = OrganizationAgent(mcp_client)

    async def run(self, dry_run: bool = False) -> list[dict]:
        """
        Discover all pages → process unprocessed ones.
        Returns list of results: [{page_id, title, status, analysis}]
        """
        pages = await self._discover_pages()
        print(f"\n[organizer] Found {len(pages)} page(s) accessible to the integration.")

        results = []
        for i, page in enumerate(pages, 1):
            page_id = page["id"]
            title = page["title"]
            print(f"\n[organizer] ({i}/{len(pages)}) '{title}'")

            if await self._is_processed(page_id):
                print(f"[organizer] Already has Second Brain Index — skipping.")
                results.append({"page_id": page_id, "title": title, "status": "skipped"})
                continue

            if dry_run:
                print(f"[organizer] [dry-run] Would process this page.")
                results.append({"page_id": page_id, "title": title, "status": "dry-run"})
                continue

            try:
                analysis = await self._agent.process_page(page_id)
                results.append({
                    "page_id": page_id,
                    "title": title,
                    "status": "done",
                    "analysis": analysis,
                })
            except Exception as e:
                print(f"[organizer] Error: {e}")
                results.append({"page_id": page_id, "title": title, "status": "error", "error": str(e)})

            # Small delay to respect Groq rate limits
            if i < len(pages):
                await asyncio.sleep(2)

        return results

    # ------------------------------------------------------------------

    async def _discover_pages(self) -> list[dict]:
        """Search for all pages the integration can access."""
        raw = await self._mcp.call_tool(
            "API-post-search",
            {
                "query": "",
                "filter": {"value": "page", "property": "object"},
                "page_size": settings.agent.batch_size,
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
            if page_id:
                pages.append({"id": page_id, "title": title})
        return pages

    async def _is_processed(self, page_id: str) -> bool:
        """Check if this page already has a Second Brain Index section."""
        try:
            raw = await self._mcp.call_tool("API-get-block-children", {"block_id": page_id})
            data = json.loads(raw)
            for block in data.get("results", []):
                btype = block.get("type", "")
                rich = block.get(btype, {}).get("rich_text", [])
                text = "".join(p.get("plain_text", "") for p in rich)
                if ALREADY_PROCESSED_MARKER in text:
                    return True
        except Exception:
            pass
        return False


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
