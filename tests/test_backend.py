import asyncio
from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.config import Settings
from backend.database import Base
from backend.integrations.mcp import MCPToolManager
from backend.repositories.conversations import ConversationRepository
from backend.schemas import ToolResult, TravelRequest
from backend.services.agent_service import TravelAgentService
from backend.services.knowledge_service import KnowledgeService
from backend.services.mcp_travel_service import MCPTravelService


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
                "client-a",
                "chengdu.md",
                "# 成都攻略\n熊猫基地建议早上8-10点参观。\n宽窄巷子适合体验历史文化。".encode(),
            )
        )

        self.assertEqual(document.status, "ready")
        self.assertGreater(document.chunk_count, 0)
        citations = asyncio.run(service.search("client-a", "熊猫几点去", top_k=2))
        self.assertTrue(citations)
        self.assertEqual(citations[0].source, "chengdu.md")
        self.assertIn("熊猫", citations[0].excerpt)
        other_user_citations = asyncio.run(service.search("client-b", "熊猫几点去", top_k=2))
        self.assertEqual(other_user_citations, [])

        reindexed = asyncio.run(service.reindex(document))
        self.assertEqual(reindexed.status, "ready")
        service.delete_document(document)
        self.assertEqual(service.list_documents("client-a"), [])

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
                "test-client",
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

    def test_agent_captures_and_reuses_long_term_memory(self):
        service = TravelAgentService(self.database, self.settings)
        service.knowledge.search = AsyncMock(return_value=[])

        with patch(
            "backend.services.agent_service.mcp_travel_service.collect",
            new=AsyncMock(return_value=[]),
        ):
            asyncio.run(
                service.chat(
                    TravelRequest(
                        query="我喜欢美食和人文景点，帮我规划成都旅行",
                        client_id="memory-client",
                    )
                )
            )

        memories = service.memories.list_memories("memory-client")
        self.assertTrue(memories)
        self.assertIn("美食", memories[0].content)

    def test_casual_chat_skips_rag_and_mcp(self):
        service = TravelAgentService(self.database, self.settings)
        service.knowledge.search = AsyncMock(return_value=[])

        with patch(
            "backend.services.agent_service.mcp_travel_service.collect",
            new=AsyncMock(return_value=[]),
        ) as collect_tools:
            response = asyncio.run(
                service.chat(
                    TravelRequest(
                        query="你好",
                        client_id="test-client",
                    )
                )
            )

        service.knowledge.search.assert_not_awaited()
        collect_tools.assert_not_awaited()
        self.assertEqual(response.citations, [])
        self.assertEqual(response.tools, [])
        self.assertIn("你好", response.answer)

    def test_train_tool_intent_requires_origin_and_destination(self):
        service = TravelAgentService(self.database, self.settings)

        extraction = service._normalize_extraction(
            "\u67e5\u8be2\u5e7f\u5dde\u8f66\u7968",
            {
                "intent": "travel_plan",
                "origin": "",
                "destination": "",
                "travel_date": "",
                "needs_rag": False,
                "tool_intents": ["train"],
            },
        )

        self.assertEqual(extraction["tool_intents"], [])

    def test_train_tool_intent_only_requires_origin_and_destination(self):
        service = TravelAgentService(self.database, self.settings)

        extraction = service._normalize_extraction(
            "\u67e5\u8be2\u5e7f\u5dde\u5230\u4e0a\u6d77\u7684\u8f66\u7968",
            {},
        )

        self.assertEqual(extraction["origin"], "\u5e7f\u5dde")
        self.assertEqual(extraction["destination"], "\u4e0a\u6d77")
        self.assertIn("train", extraction["tool_intents"])

    def test_train_query_recognizes_current_location_phrase(self):
        service = TravelAgentService(self.database, self.settings)

        extraction = service._normalize_extraction(
            "\u6211\u60f3\u53bb\u4e0a\u6d77\u73a9\u4e09\u5929\uff0c\u6211\u73b0\u5728\u5728\u5a04\u5e95\uff0c\u660e\u5929\u4e0b\u5348\u51fa\u53d1\uff0c\u6211\u8981\u5750\u9ad8\u94c1\u53bb",
            {},
        )

        self.assertEqual(extraction["origin"], "\u5a04\u5e95")
        self.assertEqual(extraction["destination"], "\u4e0a\u6d77")
        self.assertEqual(
            extraction["travel_date"],
            (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
        )
        self.assertIn("train", extraction["tool_intents"])
        self.assertFalse(service._is_complete_realtime_request(extraction))

    def test_train_query_ignores_relative_date_as_route_origin(self):
        service = TravelAgentService(self.database, self.settings)

        extraction = service._normalize_extraction(
            "我在娄底，明天去上海坐高铁",
            {},
        )

        self.assertEqual(extraction["origin"], "娄底")
        self.assertEqual(extraction["destination"], "上海")
        self.assertEqual(
            extraction["travel_date"],
            (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
        )
        self.assertEqual(extraction["tool_intents"], ["train"])
        self.assertTrue(service._is_complete_realtime_request(extraction))

    def test_direct_train_query_returns_realtime_result_without_planning(self):
        service = TravelAgentService(self.database, self.settings)

        extraction = service._normalize_extraction(
            "\u67e5\u8be2\u660e\u5929\u5e7f\u5dde\u5230\u4e0a\u6d77\u7684\u9ad8\u94c1\u7968",
            {},
        )

        self.assertEqual(extraction["travel_days"], 0)
        self.assertTrue(service._is_complete_realtime_request(extraction))

    def test_complete_planning_query_uses_model_preanalysis(self):
        service = TravelAgentService(self.database, self.settings)
        service.llm = AsyncMock()
        service.llm.ainvoke.return_value = MagicMock(
            content=(
                '{"intent":"travel_plan","destination":"上海","origin":"娄底",'
                '"travel_days":3,"travel_date":"2026-07-28","tool_intents":["train"]}'
            )
        )

        extraction = asyncio.run(
            service._extract("我想去上海玩三天，明天出发，我在娄底")
        )

        service.llm.ainvoke.assert_awaited_once()
        self.assertEqual(extraction["destination"], "上海")
        self.assertEqual(extraction["origin"], "娄底")
        self.assertEqual(extraction["travel_days"], 3)

    def test_agent_planner_selects_tools_for_complete_trip(self):
        service = TravelAgentService(self.database, self.settings)
        service.llm = AsyncMock()
        service.knowledge.search = AsyncMock(return_value=[])
        service.llm.ainvoke.return_value = MagicMock(
            content=json.dumps(
                {
                    "calls": [
                        {
                            "tool": "knowledge_search",
                            "arguments": {"query": "上海三日游景点住宿美食"},
                        },
                        {
                            "tool": "train_query",
                            "arguments": {
                                "origin": "娄底",
                                "destination": "上海",
                                "date": "2026-07-28",
                                "train_type": "G",
                            },
                        },
                    ],
                    "done": True,
                },
                ensure_ascii=False,
            )
        )
        extraction = service._normalize_extraction(
            "我想去上海玩三天，我目前在娄底，明天下午出发，我要坐高铁去",
            {},
        )

        with patch(
            "backend.services.agent_tools.mcp_travel_service.query_train",
            new=AsyncMock(
                return_value=ToolResult(
                    name="get-tickets",
                    success=True,
                    content="G1",
                )
            ),
        ):
            citations, tools = asyncio.run(
                service._collect_context(
                    TravelRequest(query="完整旅行规划", client_id="agent-client"),
                    extraction,
                )
            )

        self.assertEqual(citations, [])
        self.assertEqual({tool.name for tool in tools}, {"get-tickets"})
        service.llm.ainvoke.assert_awaited_once()

    def test_agent_planner_failure_falls_back_to_deterministic_collection(self):
        service = TravelAgentService(self.database, self.settings)
        service.llm = AsyncMock()
        service.llm.ainvoke.return_value = MagicMock(content="not-json")
        service.knowledge.search = AsyncMock(return_value=[])
        extraction = service._normalize_extraction(
            "查询明天广州到上海的高铁票",
            {},
        )

        with patch(
            "backend.services.agent_service.mcp_travel_service.collect",
            new=AsyncMock(return_value=[]),
        ) as collect_tools:
            citations, tools = asyncio.run(
                service._collect_context(
                    TravelRequest(query="查询明天广州到上海的高铁票", client_id="fallback"),
                    extraction,
                )
            )

        self.assertEqual(citations, [])
        self.assertEqual(tools, [])
        collect_tools.assert_awaited_once()

    def test_agent_planner_can_add_tools_after_observation(self):
        service = TravelAgentService(self.database, self.settings)
        service.llm = AsyncMock()
        service.knowledge.search = AsyncMock(return_value=[])
        service.llm.ainvoke.side_effect = [
            MagicMock(
                content=json.dumps(
                    {
                        "calls": [
                            {
                                "tool": "knowledge_search",
                                "arguments": {"query": "上海三日游攻略"},
                            }
                        ],
                        "done": False,
                    },
                    ensure_ascii=False,
                )
            ),
            MagicMock(
                content=json.dumps(
                    {
                        "calls": [
                            {
                                "tool": "train_query",
                                "arguments": {
                                    "origin": "娄底",
                                    "destination": "上海",
                                    "date": "2026-07-28",
                                    "train_type": "G",
                                },
                            }
                        ],
                        "done": True,
                    },
                    ensure_ascii=False,
                )
            ),
        ]
        extraction = service._normalize_extraction(
            "我想去上海玩三天，我目前在娄底，明天坐高铁出发",
            {},
        )

        with patch(
            "backend.services.agent_tools.mcp_travel_service.query_train",
            new=AsyncMock(
                return_value=ToolResult(
                    name="get-tickets",
                    success=True,
                    content="G1-result",
                )
            ),
        ):
            _, tools = asyncio.run(
                service._collect_context(
                    TravelRequest(
                        query="我想去上海玩三天，我目前在娄底，明天坐高铁出发",
                        client_id="agent-follow-up",
                    ),
                    extraction,
                )
            )

        self.assertEqual(len(tools), 1)
        self.assertEqual(service.llm.ainvoke.await_count, 2)
        second_prompt = service.llm.ainvoke.await_args_list[1].args[0]
        self.assertIn("知识库没有检索到相关资料", second_prompt)

    def test_chat_stream_emits_progress_content_and_completion(self):
        service = TravelAgentService(self.database, self.settings)
        service.knowledge.search = AsyncMock(return_value=[])

        async def collect_events():
            return [
                event
                async for event in service.chat_stream(
                    TravelRequest(query="你好", client_id="stream-client")
                )
            ]

        events = asyncio.run(collect_events())

        self.assertEqual(events[0]["type"], "progress")
        self.assertEqual(events[0]["stage"], "understanding")
        self.assertTrue(any(event["type"] == "delta" for event in events))
        self.assertEqual(events[-1]["type"], "complete")
        response = events[-1]["response"]
        self.assertEqual(response["answer"], "你好！我可以帮你规划旅行路线、整理行程、查询知识库资料，也可以在信息足够时调用实时工具。")
        self.assertIn("trip_summary", response)
        conversation = ConversationRepository(self.database).get_with_messages(
            response["conversation_id"],
            "stream-client",
        )
        self.assertEqual([message.role for message in conversation.messages], ["user", "assistant"])

    def test_train_query_recovers_missing_model_tool_intent(self):
        service = TravelAgentService(self.database, self.settings)

        extraction = service._normalize_extraction(
            "我7月31日从广州去上海，帮我查高铁",
            {
                "intent": "travel_plan",
                "origin": "广州",
                "destination": "上海",
                "travel_date": "2026-07-31",
                "needs_rag": False,
                "tool_intents": [],
            },
        )

        self.assertIn("train", extraction["tool_intents"])

    def test_mcp_text_error_is_not_reported_as_success(self):
        service = MCPTravelService()
        service._initialized = True
        service.manager.call_tool = AsyncMock(
            return_value="Error: Cannot read properties of undefined"
        )

        result = asyncio.run(
            service.call(
                "12306 Server",
                "get-tickets",
                fromStation="GZQ",
                toStation="SHH",
            )
        )

        self.assertFalse(result.success)

    def test_train_query_passes_realtime_filters(self):
        service = MCPTravelService()
        service._station_code = AsyncMock(side_effect=["GZQ", "SHH"])
        service.call = AsyncMock(
            return_value=ToolResult(name="get-tickets", success=True, content="G1")
        )

        result = asyncio.run(
            service.query_train(
                "广州",
                "上海",
                "2026-07-31",
                train_filter_flags="G",
            )
        )

        self.assertTrue(result.success)
        service.call.assert_awaited_once_with(
            "12306 Server",
            "get-tickets",
            fromStation="GZQ",
            toStation="SHH",
            date="2026-07-31",
            trainFilterFlags="G",
            sortFlag="duration",
            limitedNum=10,
            format="text",
        )

    def test_offline_answer_includes_realtime_tool_content(self):
        service = TravelAgentService(self.database, self.settings)
        tools = [
            ToolResult(
                name="get-tickets",
                success=True,
                content="G246 广州南 -> 上海虹桥 08:27 -> 15:03",
            )
        ]

        answer = service._offline_answer("查高铁", [], tools)

        self.assertIn("G246", answer)

    def test_mcp_collect_skips_initialization_without_required_arguments(self):
        service = MCPTravelService()

        with patch.object(service, "initialize", new=AsyncMock()) as initialize:
            result = asyncio.run(
                service.collect(
                    {
                        "destination": "上海",
                        "travel_date": "2026-08-10",
                        "tool_intents": [],
                    },
                    "帮我规划去上海的行程",
                )
            )

        self.assertEqual(result, [])
        initialize.assert_not_awaited()

    def test_mcp_collect_reports_missing_config_without_failing_chat(self):
        service = MCPTravelService()

        with patch.object(
            service,
            "initialize",
            new=AsyncMock(side_effect=FileNotFoundError("missing private config")),
        ):
            result = asyncio.run(
                service.collect(
                    {
                        "origin": "广州",
                        "destination": "上海",
                        "travel_date": "2026-08-10",
                        "tool_intents": ["train"],
                    },
                    "查询广州到上海的高铁",
                )
            )

        self.assertEqual(len(result), 1)
        self.assertFalse(result[0].success)
        self.assertEqual(result[0].name, "realtime-tools")
        self.assertNotIn("private config", result[0].content)

    def test_travel_mcp_service_only_loads_12306_server(self):
        config_path = Path(self.temp_dir.name) / "servers_config.json"
        config_path.write_text(
            json.dumps(
                {
                    "mcp_servers": [
                        {"name": "12306 Server", "url": "https://example.com/train"},
                        {"name": "Unsupported Server", "url": "https://example.com/other"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        service = MCPTravelService()
        service.manager = MCPToolManager(str(config_path))

        asyncio.run(service.initialize())

        self.assertEqual(set(service.manager.servers), {"12306 Server"})

    def test_mcp_health_reports_no_tools_when_config_is_missing(self):
        service = MCPTravelService()

        with patch.object(
            service,
            "initialize",
            new=AsyncMock(side_effect=FileNotFoundError("missing private config")),
        ):
            result = asyncio.run(service.health())

        self.assertEqual(result, {})

    def test_agent_uses_deepseek_chat_for_decisions(self):
        settings = Settings(
            database_url="sqlite:///:memory:",
            upload_dir=Path(self.temp_dir.name),
            dashscope_api_key="",
            deepseek_api_key="test-deepseek-key",
            deepseek_chat_model="deepseek-v4-pro",
            deepseek_base_url="https://api.deepseek.com",
            deepseek_temperature=0.7,
            embedding_dimension=4,
        )

        with patch("backend.services.agent_service.ChatOpenAI") as chat_model:
            service = TravelAgentService(self.database, settings)

        chat_model.assert_called_once_with(
            model="deepseek-v4-pro",
            api_key="test-deepseek-key",
            base_url="https://api.deepseek.com",
            temperature=0.7,
            extra_body={"thinking": {"type": "disabled"}},
        )
        self.assertIs(service.llm, chat_model.return_value)

    def test_dashscope_key_does_not_enable_chat_model(self):
        settings = Settings(
            database_url="sqlite:///:memory:",
            upload_dir=Path(self.temp_dir.name),
            dashscope_api_key="test-dashscope-key",
            deepseek_api_key="",
            embedding_dimension=4,
        )

        with patch("backend.services.agent_service.ChatOpenAI") as chat_model:
            service = TravelAgentService(self.database, settings)

        chat_model.assert_not_called()
        self.assertIsNone(service.llm)


if __name__ == "__main__":
    unittest.main()
