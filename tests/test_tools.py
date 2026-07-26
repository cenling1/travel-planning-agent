import asyncio
import json
import unittest
from unittest.mock import AsyncMock, mock_open, patch

import httpx

from backend.integrations.mcp import MCPServerConnection, MCPToolManager


class FlakyConnection:
    def __init__(self, failures):
        self.failures = failures
        self.calls = 0
        self.session_id = "test-session"

    async def call_tool(self, tool_name, arguments):
        self.calls += 1
        if self.calls <= self.failures:
            raise ConnectionError("temporary connection failure")
        return json.dumps({"tool": tool_name, "arguments": arguments})


class MCPToolManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_initialize_registers_servers_without_connecting(self):
        config = json.dumps(
            {
                "mcp_servers": [
                    {"name": "test", "url": "https://example.com/mcp"},
                    {"name": "disabled", "url": ""},
                ]
            }
        )
        manager = MCPToolManager(config_path="servers.json")

        with (
            patch("backend.integrations.mcp.os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=config)),
            patch.object(
                MCPServerConnection,
                "initialize",
                new=AsyncMock(),
            ) as initialize_connection,
        ):
            await manager.initialize()

        initialize_connection.assert_not_awaited()
        self.assertEqual(list(manager.servers), ["test"])

    async def test_retries_transient_connection_failures(self):
        manager = MCPToolManager(config_path="unused.json")
        connection = FlakyConnection(failures=2)
        manager.servers["test"] = connection

        with patch.object(asyncio, "sleep", new=AsyncMock()):
            result = await manager.call_tool(
                "test",
                "lookup",
                max_retries=2,
                city="Shanghai",
            )

        self.assertEqual(connection.calls, 3)
        self.assertEqual(json.loads(result)["arguments"], {"city": "Shanghai"})

    async def test_does_not_retry_application_errors(self):
        manager = MCPToolManager(config_path="unused.json")
        connection = FlakyConnection(failures=0)

        async def fail_with_application_error(tool_name, arguments):
            connection.calls += 1
            raise RuntimeError("invalid tool arguments")

        connection.call_tool = fail_with_application_error
        manager.servers["test"] = connection

        result = await manager.call_tool("test", "lookup", max_retries=2)

        self.assertEqual(connection.calls, 1)
        self.assertIn("invalid tool arguments", json.loads(result)["error"])

    async def test_reinitializes_and_retries_expired_session(self):
        manager = MCPToolManager(config_path="unused.json")
        connection = FlakyConnection(failures=0)

        async def expire_once(tool_name, arguments):
            connection.calls += 1
            if connection.calls == 1:
                request = httpx.Request("POST", "https://private.example/mcp")
                response = httpx.Response(401, request=request)
                raise httpx.HTTPStatusError(
                    "401 Unauthorized for private endpoint",
                    request=request,
                    response=response,
                )
            connection.session_id = "renewed-session"
            return json.dumps({"tool": tool_name, "arguments": arguments})

        connection.call_tool = expire_once
        manager.servers["test"] = connection

        with patch.object(asyncio, "sleep", new=AsyncMock()):
            result = await manager.call_tool("test", "lookup", city="Shanghai")

        self.assertEqual(connection.calls, 2)
        self.assertEqual(json.loads(result)["arguments"], {"city": "Shanghai"})

    async def test_http_errors_do_not_expose_private_endpoint(self):
        manager = MCPToolManager(config_path="unused.json")
        connection = FlakyConnection(failures=0)

        async def always_unauthorized(_tool_name, _arguments):
            request = httpx.Request("POST", "https://private.example/mcp")
            response = httpx.Response(401, request=request)
            raise httpx.HTTPStatusError(
                "401 Unauthorized for https://private.example/mcp",
                request=request,
                response=response,
            )

        connection.call_tool = always_unauthorized
        manager.servers["test"] = connection

        with patch.object(asyncio, "sleep", new=AsyncMock()):
            result = await manager.call_tool("test", "lookup", max_retries=0)

        error = json.loads(result)["error"]
        self.assertIn("HTTP 401 Unauthorized", error)
        self.assertNotIn("private.example", error)
if __name__ == "__main__":
    unittest.main()
