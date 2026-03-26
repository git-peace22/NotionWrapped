"""
Test the agent on a single page.
Usage: python test_agent.py <page_id>

Get the page_id from the Notion page URL:
  https://notion.so/My-Page-Title-<page_id>
  The page_id is the last part (32 hex chars, with or without dashes).
"""

import asyncio
import sys
from src.mcp.client import notion_mcp
from src.agent.core import OrganizationAgent


async def main(page_id: str):
    async with notion_mcp() as client:
        agent = OrganizationAgent(client)
        await agent.process_page(page_id)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_agent.py <page_id>")
        print("\nGet the page_id from the page URL in Notion.")
        sys.exit(1)

    asyncio.run(main(sys.argv[1]))
