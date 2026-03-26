"""
Quick smoke test — connect to Notion MCP, print discovered tools.
Run: python test_connection.py
"""

import asyncio
from src.mcp.client import notion_mcp


async def main():
    print("Connecting to Notion MCP server...")
    async with notion_mcp() as client:
        tools = client.list_tools()
        print(f"\n✓ Connected. {len(tools)} tools discovered:\n")
        for tool in tools:
            print(f"  • {tool.name}")
            if tool.description:
                # Print first line of description only
                print(f"      {tool.description.splitlines()[0]}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
