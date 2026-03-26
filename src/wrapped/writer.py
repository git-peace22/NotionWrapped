"""
Notion page writer — builds and writes the "🎉 Your Notion Wrapped" page.
"""

import json
from src.mcp.client import NotionMCPClient


class WrappedWriter:

    def __init__(self, mcp_client: NotionMCPClient):
        self._mcp = mcp_client

    async def write(
        self,
        stats: dict,
        analysis: dict,
        pages: list[dict],
        parent_page_id: str,
    ) -> str:
        """
        Create the Notion Wrapped page as a child of parent_page_id.
        Returns the URL of the created page.
        """
        hidden_gem_id = analysis.get("hidden_gem_id", "")
        hidden_gem_title = next(
            (p["title"] for p in pages if p["id"] == hidden_gem_id), "Unknown"
        )
        hidden_gem_reason = analysis.get("hidden_gem_reason", "")

        blocks = _build_wrapped_blocks(stats, analysis, hidden_gem_title, hidden_gem_reason)

        # Create the page
        create_result = await self._mcp.call_tool(
            "API-post-page",
            {
                "parent": {"type": "page_id", "page_id": parent_page_id},
                "properties": {
                    "title": [{"type": "text", "text": {"content": "🎉 Your Notion Wrapped"}}]
                },
            },
        )

        page_data = json.loads(create_result)
        page_id = page_data.get("id", "")
        page_url = page_data.get("url", "")

        # Write blocks in batches (Notion limit ~100 per call)
        for i in range(0, len(blocks), 90):
            batch = blocks[i : i + 90]
            await self._mcp.call_tool(
                "API-patch-block-children",
                {"block_id": page_id, "children": batch},
            )

        return page_url


def _build_wrapped_blocks(
    stats: dict,
    analysis: dict,
    hidden_gem_title: str,
    hidden_gem_reason: str,
) -> list[dict]:
    blocks = []

    total_pages = stats.get("total_pages", 0)
    total_words = stats.get("total_words", 0)
    date_range_str = stats.get("date_range_str", "Unknown")
    hottest_month = stats.get("hottest_month", "Unknown")
    hottest_month_count = stats.get("hottest_month_count", 0)
    graveyard = stats.get("graveyard", [])
    graveyard_total = stats.get("graveyard_total", 0)
    longest_abandoned_title = stats.get("longest_abandoned_title", "Unknown")
    longest_abandoned_days = stats.get("longest_abandoned_days", 0)

    top_obsessions = analysis.get("top_obsessions", [])
    roast_lines = analysis.get("roast_lines", [])
    one_word = analysis.get("one_word_summary", "Thinker")

    # ── Header ──────────────────────────────────────────────────────────
    blocks.append(_h1("🎉 Your Notion Wrapped"))
    blocks.append(_paragraph(f"An AI-powered analysis of your entire brain. Covering {date_range_str}."))
    blocks.append(_divider())

    # ── By the Numbers ───────────────────────────────────────────────────
    blocks.append(_h2("📊 By the Numbers"))
    blocks.append(_callout(
        f"🗒️  {total_pages} pages   ·   ✍️  {total_words:,} words   ·   📅  {date_range_str}",
        emoji="📊",
        color="blue_background",
    ))
    blocks.append(_divider())

    # ── Top Obsessions ───────────────────────────────────────────────────
    blocks.append(_h2("🔥 Your Top Obsessions"))
    blocks.append(_paragraph("The themes you keep coming back to, whether you realize it or not:"))
    for topic in top_obsessions:
        blocks.append(_bullet(f"  {topic}"))
    blocks.append(_divider())

    # ── Hottest Month ────────────────────────────────────────────────────
    blocks.append(_h2("📅 Your Most Productive Month"))
    blocks.append(_callout(
        f"🏆  {hottest_month} — you created {hottest_month_count} page{'s' if hottest_month_count != 1 else ''} that month.",
        emoji="📅",
        color="green_background",
    ))
    blocks.append(_divider())

    # ── Graveyard ────────────────────────────────────────────────────────
    blocks.append(_h2("🪦 The Graveyard"))
    if graveyard_total > 0:
        blocks.append(_paragraph(
            f"{graveyard_total} idea{'s' if graveyard_total != 1 else ''} started, never revisited. "
            f"The longest-abandoned note? \"{longest_abandoned_title}\" — untouched for {longest_abandoned_days} days."
        ))
        for title in graveyard[:5]:
            blocks.append(_bullet(f"💀  {title}"))
    else:
        blocks.append(_paragraph("No abandoned notes detected. Either you're incredibly disciplined, or you delete your failures."))
    blocks.append(_divider())

    # ── Hidden Gem ───────────────────────────────────────────────────────
    blocks.append(_h2("💎 Hidden Gem"))
    blocks.append(_paragraph("The note you wrote and completely forgot about. It deserves a second look."))
    blocks.append(_quote(f'"{hidden_gem_title}"\n{hidden_gem_reason}'))
    blocks.append(_divider())

    # ── Roast ────────────────────────────────────────────────────────────
    blocks.append(_h2("🎤 Your Notion Roast"))
    blocks.append(_paragraph("We read everything. Here's what the AI found."))
    for line in roast_lines:
        blocks.append(_callout(line, emoji="🔥", color="red_background"))
    blocks.append(_divider())

    # ── One Word ─────────────────────────────────────────────────────────
    blocks.append(_callout(
        f"🧠  One word to describe your brain:  {one_word.upper()}",
        emoji="🧠",
        color="yellow_background",
    ))
    blocks.append(_divider())

    # ── Footer ───────────────────────────────────────────────────────────
    blocks.append(_paragraph("Generated by Notion Wrapped · Notion × MLH Hackathon 2025"))

    return blocks


# ── Block builder helpers ────────────────────────────────────────────────────

def _h1(text: str) -> dict:
    return {"object": "block", "type": "heading_1",
            "heading_1": {"rich_text": [{"type": "text", "text": {"content": text}}]}}

def _h2(text: str) -> dict:
    return {"object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": text}}]}}

def _paragraph(text: str) -> dict:
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]}}

def _bullet(text: str) -> dict:
    return {"object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": text}}]}}

def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}

def _quote(text: str) -> dict:
    return {"object": "block", "type": "quote",
            "quote": {"rich_text": [{"type": "text", "text": {"content": text}}]}}

def _callout(text: str, emoji: str = "💡", color: str = "blue_background") -> dict:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {"content": text}}],
            "icon": {"type": "emoji", "emoji": emoji},
            "color": color,
        },
    }
