import asyncio
import json
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

from langchain_core.documents import Document

from travel_agent.tools.mcp_tools import MCPServerConnection, MCPToolManager
from travel_agent.tools.rag_tool import TravelRAG


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
            patch("travel_agent.tools.mcp_tools.os.path.exists", return_value=True),
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


class TravelRAGTests(unittest.TestCase):
    @patch("travel_agent.tools.rag_tool.DashScopeEmbeddings")
    @patch("travel_agent.tools.rag_tool.Chroma")
    def test_existing_vector_store_is_loaded_after_restart(
        self,
        chroma_class,
        _embeddings_class,
    ):
        vector_store = MagicMock()
        vector_store.get.return_value = {"ids": ["chunk-1", "chunk-2"]}
        chroma_class.return_value = vector_store

        with tempfile.TemporaryDirectory() as persist_directory:
            rag = TravelRAG(
                persist_directory=persist_directory,
                embedding_api_key="test-key",
            )

        chroma_class.assert_called_once_with(
            persist_directory=persist_directory,
            embedding_function=rag.embeddings,
            collection_name="travel_knowledge",
        )
        vector_store.as_retriever.assert_called_once()
        self.assertEqual(rag.imported_ids, {"chunk-1", "chunk-2"})
        self.assertIsNotNone(rag.retriever)

    def test_document_ids_are_stable_and_content_sensitive(self):
        first = Document(page_content="West Lake guide", metadata={"source": "hangzhou.md"})
        same = Document(page_content="West Lake guide", metadata={"source": "hangzhou.md"})
        changed = Document(page_content="Updated West Lake guide", metadata={"source": "hangzhou.md"})

        first_id = TravelRAG.generate_doc_id(first, chunk_index=0)

        self.assertEqual(first_id, TravelRAG.generate_doc_id(same, chunk_index=0))
        self.assertNotEqual(first_id, TravelRAG.generate_doc_id(changed, chunk_index=0))
        self.assertNotEqual(first_id, TravelRAG.generate_doc_id(first, chunk_index=1))


if __name__ == "__main__":
    unittest.main()
