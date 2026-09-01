"""Thin async wrapper around Alpaca's official MCP server.

Satisfies the hackathon's "MCP or CLI" core requirement: every account,
market-data, and order-placement operation the agent performs goes through
`alpaca-mcp-server` (spawned locally via `uvx`) over the Model Context
Protocol — never a direct alpaca-py trading call.
"""
import json
import os
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent.config import CONFIG


class AlpacaMCPClient:
    def __init__(self, toolsets: str = None):
        env = {
            **os.environ,
            "ALPACA_API_KEY": CONFIG.alpaca_api_key,
            "ALPACA_SECRET_KEY": CONFIG.alpaca_secret_key,
            "ALPACA_PAPER_TRADE": "true" if CONFIG.alpaca_paper else "false",
        }
        if toolsets:
            env["ALPACA_TOOLSETS"] = toolsets
        self._params = StdioServerParameters(command="uvx", args=["alpaca-mcp-server"], env=env)
        self._stack = AsyncExitStack()
        self.session: ClientSession = None

    async def __aenter__(self):
        read, write = await self._stack.enter_async_context(stdio_client(self._params))
        self.session = await self._stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()
        return self

    async def __aexit__(self, *exc):
        await self._stack.aclose()

    async def list_tools_anthropic_format(self) -> list:
        """Fetch the server's tool list and convert it to Anthropic tool-use schema."""
        result = await self.session.list_tools()
        tools = []
        for t in result.tools:
            # The MCP Python SDK renamed Tool.inputSchema -> Tool.input_schema. Reading only
            # the old name raised AttributeError on every call under the installed SDK, which
            # took out both LLM paths (live_agent, multi_agent) on their first MCP round trip
            # -- the deterministic path never calls this, which is why it kept working and hid
            # the break. Accept either spelling rather than pinning the SDK version.
            schema = getattr(t, "input_schema", None) or getattr(t, "inputSchema", None)
            tools.append({
                "name": t.name,
                "description": t.description or "",
                "input_schema": schema or {"type": "object", "properties": {}},
            })
        return tools

    async def call_tool(self, name: str, arguments: dict) -> str:
        result = await self.session.call_tool(name, arguments)
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
            else:
                parts.append(json.dumps(getattr(block, "data", str(block))))
        text = "\n".join(parts)
        if getattr(result, "isError", False):
            return json.dumps({"error": text})
        return text
