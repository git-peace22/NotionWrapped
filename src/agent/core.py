"""
Agent core — hybrid approach:
  1. Read page content directly via MCP (Python, no LLM overhead)
  2. LLM analyzes content → structured output (category, tags, summary)
  3. Write results back via MCP directly (Python, no LLM overhead)

This keeps LLM token usage minimal and the pipeline reliable.
"""

import json
from groq import AsyncGroq

from src.config import settings
from src.mcp.client import NotionMCPClient
from src.agent.prompts import ANALYZE_PROMPT


class OrganizationAgent:

    def __init__(self, mcp_client: NotionMCPClient):
        self._mcp = mcp_client
        self._groq = AsyncGroq(api_key=settings.groq_api_key)

    async def process_page(self, page_id: str) -> dict:
        """
        Full organize pipeline for a single page.
        Returns the analysis dict: {category, tags, summary}.
        """
        print(f"\n[agent] Processing page: {page_id}")

        # Step 1: Read page content via MCP
        content = await self._read_page(page_id)
        if not content.strip():
            print("[agent] Page has no readable content, skipping.")
            return {}

        # Step 2: LLM analysis — category, tags, summary
        analysis = await self._analyze(content)
        print(f"[agent] Analysis: {analysis}")

        # Step 3: Write Second Brain Index back to Notion
        await self._write_index(page_id, analysis)
        print(f"[agent] Written back to Notion.")

        return analysis

    # ------------------------------------------------------------------
    # Step 1: Read
    # ------------------------------------------------------------------

    async def _read_page(self, page_id: str) -> str:
        """Fetch page title + block text content via MCP."""
        # Get page metadata (title)
        page_raw = await self._mcp.call_tool("API-retrieve-a-page", {"page_id": page_id})
        title = _extract_title(page_raw)

        # Get block content
        blocks_raw = await self._mcp.call_tool("API-get-block-children", {"block_id": page_id})
        body = _extract_text_from_blocks(blocks_raw)

        content = f"Title: {title}\n\n{body}"
        # Truncate to ~3000 words to stay within token limits
        words = content.split()
        if len(words) > 3000:
            content = " ".join(words[:3000]) + "\n[truncated]"

        print(f"[agent] Read {len(words)} words from '{title}'")
        return content

    # ------------------------------------------------------------------
    # Step 2: Analyze
    # ------------------------------------------------------------------

    async def _analyze(self, content: str) -> dict:
        """Call LLM to categorize, tag, and summarize the content."""
        response = await self._groq.chat.completions.create(
            model=settings.agent.model,
            messages=[
                {"role": "system", "content": ANALYZE_PROMPT},
                {"role": "user", "content": content},
            ],
            temperature=0.2,
            max_tokens=512,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"category": "Other", "tags": [], "summary": raw}

    # ------------------------------------------------------------------
    # Step 3: Write
    # ------------------------------------------------------------------

    async def _write_index(self, page_id: str, analysis: dict) -> None:
        """
        Write Second Brain Index to the page.
        Deletes any existing index blocks first to avoid duplicates, then appends.
        """
        raw = await self._mcp.call_tool("API-get-block-children", {"block_id": page_id})
        data = json.loads(raw)
        existing_blocks = data.get("results", [])

        # Delete any existing Second Brain Index blocks (sequential — avoids Notion rate limits)
        for block in existing_blocks:
            if _is_index_block(block):
                try:
                    await self._mcp.call_tool("API-delete-a-block", {"block_id": block["id"]})
                except Exception:
                    pass

        # Append fresh index
        await self._mcp.call_tool(
            "API-patch-block-children",
            {"block_id": page_id, "children": _build_index_blocks(analysis)},
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _is_index_block(block: dict) -> bool:
    """Return True if this block is part of a previously written Second Brain Index."""
    btype = block.get("type", "")
    content = block.get(btype, {})
    rich = content.get("rich_text", [])
    text = "".join(p.get("plain_text", "") for p in rich)
    return "🧠 Second Brain Index" in text


def _build_index_blocks(analysis: dict) -> list[dict]:
    category = analysis.get("category", "Other")
    tags = analysis.get("tags", [])
    summary = analysis.get("summary", "")
    tags_str = "  ".join(f"`{t}`" for t in tags)
    return [
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [
                    {"type": "text", "text": {"content": "🧠 Second Brain Index\n"},"annotations": {"bold": True}},
                    {"type": "text", "text": {"content": f"📂 {category}   🏷️ {tags_str}\n📝 {summary}"}},
                ],
                "icon": {"type": "emoji", "emoji": "🧠"},
                "color": "blue_background",
            },
        },
    ]


def _extract_title(page_raw: str) -> str:
    try:
        data = json.loads(page_raw)
        props = data.get("properties", {})
        for prop in props.values():
            if prop.get("type") == "title":
                parts = prop.get("title", [])
                return "".join(p.get("plain_text", "") for p in parts)
    except Exception:
        pass
    return "Untitled"


def _extract_text_from_blocks(blocks_raw: str) -> str:
    """Recursively extract plain text from Notion block list JSON."""
    try:
        data = json.loads(blocks_raw)
        results = data.get("results", [])
    except Exception:
        return blocks_raw

    lines = []
    for block in results:
        text = _block_text(block)
        if text:
            lines.append(text)
    return "\n".join(lines)


def _block_text(block: dict) -> str:
    """Extract plain text from a single block."""
    btype = block.get("type", "")
    content = block.get(btype, {})
    rich = content.get("rich_text", [])
    return "".join(p.get("plain_text", "") for p in rich)


def _text_block(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        },
    }
