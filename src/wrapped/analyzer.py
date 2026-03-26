"""
LLM analyzer — single Groq call to extract obsessions, roast lines, hidden gem.
Keeps token usage minimal: title + 200-word snippet per page.
"""

import json
from groq import AsyncGroq

from src.config import settings


WRAPPED_PROMPT = """You are analyzing someone's Notion workspace to generate their "Notion Wrapped" — a fun, Spotify Wrapped-style year-in-review for their brain.

Given a list of pages (id, title, content snippet), return a JSON object with exactly these fields:
{
  "top_obsessions": ["topic1", "topic2", "topic3", "topic4", "topic5"],
  "roast_lines": [
    "roast line 1",
    "roast line 2",
    "roast line 3"
  ],
  "hidden_gem_id": "<page_id exactly as given>",
  "hidden_gem_reason": "one sentence explaining why this page is interesting and underrated",
  "one_word_summary": "one word that describes this person's entire brain"
}

Rules:
- top_obsessions: The 5 most recurring topics/themes across all pages. Short phrases (1-3 words).
- roast_lines: Genuinely funny, slightly brutal but never mean. Use specific evidence from their notes. Example style: "You have 8 notes titled 'Important' with nothing important in any of them." or "Every third page starts with 'This time I'll actually finish this.'"
- hidden_gem_id: Pick the page_id (copy it exactly) of the most interesting, underrated, or surprisingly insightful forgotten page.
- hidden_gem_reason: One specific sentence about why this page deserves a second look.
- one_word_summary: A single evocative word (e.g. "Overthinker", "Dreamer", "Optimizer", "Hoarder", "Visionary").

Return only valid JSON, no extra text."""


class WrappedAnalyzer:

    def __init__(self):
        self._groq = AsyncGroq(api_key=settings.groq_api_key)

    async def analyze(self, pages: list[dict]) -> dict:
        """Single LLM call — analyze all pages, return insights."""
        pages_text = self._build_pages_text(pages)

        response = await self._groq.chat.completions.create(
            model=settings.agent.model,
            messages=[
                {"role": "system", "content": WRAPPED_PROMPT},
                {"role": "user", "content": pages_text},
            ],
            temperature=0.7,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def _build_pages_text(self, pages: list[dict]) -> str:
        lines = [f"Here are {len(pages)} pages from this person's Notion workspace:\n"]
        for p in pages:
            snippet = p.get("snippet", "").strip()
            display = snippet[:300] if snippet else "(empty page)"
            lines.append(f'- id: {p["id"]} | title: "{p["title"]}" | content: {display}')
        return "\n".join(lines)
