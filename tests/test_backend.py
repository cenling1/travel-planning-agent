import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.config import Settings
from backend.database import Base
from backend.repositories.conversations import ConversationRepository
from backend.schemas import TravelRequest
from backend.services.agent_service import TravelAgentService
from backend.services.knowledge_service import KnowledgeService


class FakeEmbeddingService:
    provider = "test-embedding"

    async def embed_documents(self, texts):
        return [self._embed(text) for text in texts]

    async def embed_query(self, text):
        return self._embed(text)

    @staticmethod
    def _embed(text):
        vector = [
            float(text.count("熊猫")),
            float(text.count("故宫")),
            float(text.count("上海")),
            float(max(1, len(text) % 11)),
        ]
        norm = sum(value * value for value in vector) ** 0.5 or 1.0
        return [value / norm for value in vector]


class BackendServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.database = Session(self.engine)
        self.settings = Settings(
            database_url="sqlite:///:memory:",
            upload_dir=Path(self.temp_dir.name),
            dashscope_api_key="",
            deepseek_api_key="",
            embedding_dimension=4,
            chunk_size=120,
            chunk_overlap=10,
            search_k=3,
        )

    def tearDown(self):
        self.database.close()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_document_lifecycle_and_hybrid_search(self):
        service = KnowledgeService(
            self.database,
            self.settings,
            embeddings=FakeEmbeddingService(),
        )
        document = asyncio.run(
            service.ingest(
                "chengdu.md",
                "# 成都攻略\n熊猫基地建议早上8-10点参观。\n宽窄巷子适合体验历史文化。".encode(),
            )
        )

        self.assertEqual(document.status, "ready")
        self.assertGreater(document.chunk_count, 0)
        citations = asyncio.run(service.search("熊猫几点去", top_k=2))
        self.assertTrue(citations)
        self.assertEqual(citations[0].source, "chengdu.md")
        self.assertIn("熊猫", citations[0].excerpt)

        reindexed = asyncio.run(service.reindex(document))
        self.assertEqual(reindexed.status, "ready")
        service.delete_document(document)
        self.assertEqual(service.list_documents(), [])

    def test_conversations_are_scoped_by_client_id(self):
        repository = ConversationRepository(self.database)
        conversation = repository.create("client-a")
        repository.add_message(conversation, "user", "规划成都三日游")

        self.assertIsNotNone(repository.get(conversation.id, "client-a"))
        self.assertIsNone(repository.get(conversation.id, "client-b"))
        detail = repository.get_with_messages(conversation.id, "client-a")
        self.assertEqual(len(detail.messages), 1)

    def test_agent_persists_messages_and_returns_citations_offline(self):
        knowledge = KnowledgeService(
            self.database,
            self.settings,
            embeddings=FakeEmbeddingService(),
        )
        asyncio.run(
            knowledge.ingest(
                "guide.txt",
                "成都熊猫基地建议早上8-10点前往。".encode(),
            )
        )
        service = TravelAgentService(self.database, self.settings)
        service.knowledge = knowledge

        with patch(
            "backend.services.agent_service.mcp_travel_service.collect",
            new=AsyncMock(return_value=[]),
        ):
            response = asyncio.run(
                service.chat(
                    TravelRequest(
                        query="成都熊猫基地几点去？",
                        client_id="test-client",
                    )
                )
            )

        self.assertTrue(response.citations)
        self.assertIn("[来源1]", response.answer)
        conversation = ConversationRepository(self.database).get_with_messages(
            response.conversation_id,
            "test-client",
        )
        self.assertEqual([message.role for message in conversation.messages], ["user", "assistant"])


if __name__ == "__main__":
    unittest.main()
