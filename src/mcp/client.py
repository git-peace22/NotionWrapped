"""
MCP Client — connects to Notion MCP server, discovers tools dynamically,
and provides a clean interface for the agent to call them.
"""

import json
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Tool

from src.config import settings


class NotionMCPClient:
    """
    Wraps the MCP session lifecycle and exposes:
    - list_tools()      → available Notion tools as Anthropic-compatible dicts
    - call_tool(name, input) → tool result as string
    """

    def __init__(self, token: str | None = None):
        self._session: ClientSession | None = None
        self._tools: list[Tool] = []
        self._token = token or settings.notion_api_token

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def connect(self):
        """Start the Notion MCP server process and open a session."""
        server_params = StdioServerParameters(
            command=settings.notion.mcp_server_command,
            args=settings.notion.mcp_server_args,
            env={"OPENAPI_MCP_HEADERS": json.dumps({
                "Authorization": f"Bearer {self._token}",
                "Notion-Version": "2022-06-28",
            })},
        )
        self._streams = stdio_client(server_params)
        read, write = await self._streams.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()
        await self._refresh_tools()
        return self

    async def disconnect(self):
        if self._session:
            await self._session.__aexit__(None, None, None)
        if self._streams:
            await self._streams.__aexit__(None, None, None)

    # ------------------------------------------------------------------
    # Tool discovery
    # ------------------------------------------------------------------

    async def _refresh_tools(self):
        result = await self._session.list_tools()
        self._tools = result.tools

    def list_tools(self) -> list[Tool]:
        return self._tools

    def as_groq_tools(self, only: list[str] | None = None) -> list[dict]:
        """
        Convert MCP tool definitions → Groq/OpenAI function calling format.
        Pass `only` to restrict to a subset of tool names.
        """
        tools = self._tools
        if only:
            tools = [t for t in tools if t.name in only]
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema or {"type": "object", "properties": {}},
                },
            }
            for tool in tools
        ]

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    async def call_tool(self, name: str, tool_input: dict[str, Any]) -> str:
        """Execute a Notion MCP tool and return its text content."""
        if not self._session:
            raise RuntimeError("MCP client not connected. Call connect() first.")

        result = await self._session.call_tool(name, tool_input)

        # Flatten content blocks into a single string
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
            else:
                parts.append(str(block))

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    async def __aenter__(self):
        return await self.connect()

    async def __aexit__(self, *args):
        await self.disconnect()


# ------------------------------------------------------------------
# Convenience: async context manager for one-off usage
# ------------------------------------------------------------------

@asynccontextmanager
async def notion_mcp(token: str | None = None):
    client = NotionMCPClient(token=token)
    try:
        await client.connect()
        yield client
    finally:
        await client.disconnect()
