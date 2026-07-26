import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import re
from typing import Any

from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..integrations.reasoning import DeepSeekR1Analyzer
from ..repositories.conversations import ConversationRepository
from ..schemas import Citation, ToolResult, TravelRequest, TravelResponse, TripSummary
from .agent_tools import AGENT_TOOL_NAMES, TravelToolExecutor, tool_catalog
from .knowledge_service import KnowledgeService
from .memory_service import MemoryService
from .mcp_travel_service import mcp_travel_service


@dataclass
class PreparedChat:
    conversation_id: str
    history: list[Any]
    extraction: dict
    citations: list[Citation]
    tools: list[ToolResult]
    scenario_type: str
    memory_context: str


class TravelAgentService:
    def __init__(self, database: Session, settings: Settings | None = None):
        self.database = database
        self.settings = settings or get_settings()
        self.conversations = ConversationRepository(database)
        self.knowledge = KnowledgeService(database, self.settings)
        self.memories = MemoryService(database)
        self.llm = None
        if self.settings.deepseek_api_key:
            self.llm = ChatOpenAI(
                model=self.settings.deepseek_chat_model,
                api_key=self.settings.deepseek_api_key,
                base_url=self.settings.deepseek_base_url,
                temperature=self.settings.deepseek_temperature,
                extra_body={
                    "thinking": {
                        "type": "enabled" if self.settings.deepseek_thinking_enabled else "disabled"
                    }
                },
            )

    async def chat(self, request: TravelRequest) -> TravelResponse:
        prepared = await self._prepare_chat(request)
        answer = await self._complete_answer(request.query, prepared)
        return self._save_response(prepared, answer)

    async def chat_stream(self, request: TravelRequest) -> AsyncIterator[dict[str, Any]]:
        conversation, history = self._start_chat(request)
        yield {"type": "progress", "stage": "understanding", "message": "正在理解旅行需求"}

        extraction = self._normalize_extraction(
            request.query,
            await self._extract(request.query),
        )
        self.memories.capture_from_query(request.client_id, request.query, extraction)
        memories = self.memories.list_memories(request.client_id)
        scenario_type = self._scenario_type(request.query, extraction)

        yield {"type": "progress", "stage": "research", "message": "正在检索资料和实时信息"}
        citations, tools = await self._collect_context(request, extraction)
        prepared = PreparedChat(
            conversation_id=conversation.id,
            history=history,
            extraction=extraction,
            citations=citations,
            tools=tools,
            scenario_type=scenario_type,
            memory_context=self.memories.format_for_prompt(memories),
        )

        yield {"type": "progress", "stage": "writing", "message": "正在生成旅行方案"}
        chunks: list[str] = []
        async for chunk in self._stream_answer(request.query, prepared):
            chunks.append(chunk)
            yield {"type": "delta", "content": chunk}

        answer = self._ensure_citations("".join(chunks).strip(), citations)
        streamed_references = answer[len("".join(chunks).strip()) :]
        if streamed_references:
            yield {"type": "delta", "content": streamed_references}
        response = self._save_response(prepared, answer)
        yield {"type": "complete", "response": response.model_dump(mode="json")}

    async def _prepare_chat(self, request: TravelRequest) -> PreparedChat:
        conversation, history = self._start_chat(request)
        extraction = self._normalize_extraction(request.query, await self._extract(request.query))
        self.memories.capture_from_query(request.client_id, request.query, extraction)
        memories = self.memories.list_memories(request.client_id)
        citations, tools = await self._collect_context(request, extraction)
        return PreparedChat(
            conversation_id=conversation.id,
            history=history,
            extraction=extraction,
            citations=citations,
            tools=tools,
            scenario_type=self._scenario_type(request.query, extraction),
            memory_context=self.memories.format_for_prompt(memories),
        )

    def _start_chat(self, request: TravelRequest):
        conversation = None
        if request.conversation_id:
            conversation = self.conversations.get(request.conversation_id, request.client_id)
            if conversation is None:
                raise ValueError("会话不存在或不属于当前客户端")
        else:
            conversation = self.conversations.create(request.client_id)

        self.conversations.add_message(conversation, "user", request.query)
        history = self.conversations.recent_messages(conversation.id, limit=12)
        return conversation, history

    async def _collect_context(
        self,
        request: TravelRequest,
        extraction: dict,
    ) -> tuple[list[Citation], list[ToolResult]]:
        if self.llm and extraction.get("intent") != "casual":
            agent_context = await self._collect_context_with_agent(request, extraction)
            if agent_context is not None:
                return agent_context
        return await self._collect_context_fallback(request, extraction)

    async def _collect_context_fallback(
        self,
        request: TravelRequest,
        extraction: dict,
    ) -> tuple[list[Citation], list[ToolResult]]:
        citations: list[Citation] = []
        tool_results: list[ToolResult] = []
        search_task = (
            self._search_with_timeout(request.client_id, request.query)
            if self._should_search_knowledge(request.query, extraction)
            else None
        )
        tools_task = (
            self._tools_with_timeout(extraction, request.query)
            if self._should_collect_tools(extraction)
            else None
        )
        if search_task and tools_task:
            citations, tool_results = await asyncio.gather(search_task, tools_task)
        elif search_task:
            citations = await search_task
        elif tools_task:
            tool_results = await tools_task
        return citations, tool_results

    async def _collect_context_with_agent(
        self,
        request: TravelRequest,
        extraction: dict,
    ) -> tuple[list[Citation], list[ToolResult]] | None:
        executor = TravelToolExecutor(
            knowledge=self.knowledge,
            owner_id=request.client_id,
            default_query=request.query,
        )
        observations: list[dict[str, Any]] = []
        citations_by_chunk: dict[str, Citation] = {}
        tool_results: list[ToolResult] = []
        executed_calls: set[str] = set()

        for round_index in range(max(1, self.settings.agent_max_rounds)):
            try:
                calls, done = await asyncio.wait_for(
                    self._plan_agent_tools(
                        request.query,
                        extraction,
                        observations,
                        executed_calls,
                        round_index,
                    ),
                    timeout=self.settings.llm_extraction_timeout_seconds,
                )
            except Exception:
                return None if not executed_calls else self._finalize_agent_context(
                    citations_by_chunk,
                    tool_results,
                )

            pending_calls: list[tuple[str, dict[str, Any], str]] = []
            for call in calls:
                tool_name = str(call.get("tool") or "").strip()
                arguments = call.get("arguments") or {}
                if tool_name not in AGENT_TOOL_NAMES or not isinstance(arguments, dict):
                    continue
                call_key = json.dumps(
                    [tool_name, arguments],
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                )
                if call_key in executed_calls:
                    continue
                pending_calls.append((tool_name, arguments, call_key))
                if len(executed_calls) + len(pending_calls) >= self.settings.agent_max_tool_calls:
                    break

            if pending_calls:
                outcomes = await asyncio.gather(
                    *(executor.execute(tool_name, arguments) for tool_name, arguments, _ in pending_calls)
                )
                for (tool_name, arguments, call_key), outcome in zip(pending_calls, outcomes):
                    executed_calls.add(call_key)
                    observations.append(
                        {
                            "tool": tool_name,
                            "arguments": arguments,
                            "observation": outcome.observation[:4000],
                        }
                    )
                    for citation in outcome.citations:
                        citations_by_chunk[citation.chunk_id] = citation
                    if outcome.result is not None:
                        tool_results.append(outcome.result)

            if done or not pending_calls or len(executed_calls) >= self.settings.agent_max_tool_calls:
                break

        if not executed_calls:
            return None
        return self._finalize_agent_context(citations_by_chunk, tool_results)

    async def _plan_agent_tools(
        self,
        query: str,
        extraction: dict,
        observations: list[dict[str, Any]],
        executed_calls: set[str],
        round_index: int,
    ) -> tuple[list[dict[str, Any]], bool]:
        prompt = f"""你是旅行 Agent 的工具规划器，负责根据用户真实需求自主选择工具。
当前日期：{datetime.now():%Y-%m-%d}

工作方式类似 ReAct：先查看需求和已有 Observation，再决定下一批 Action。
完整旅行规划可组合知识库与 12306 车次结果；景点、住宿、美食等内容优先检索知识库。
目前唯一的实时外部工具是 12306，天气、航班等信息不要尝试调用不存在的工具。
不要调用缺少必要参数的工具，不要重复相同工具和相同参数。
工具失败时可选择替代工具或结束，禁止虚构工具结果。

可用工具：
{json.dumps(tool_catalog(), ensure_ascii=False)}

结构化需求：
{json.dumps(extraction, ensure_ascii=False)}

用户原始需求：
{query}

已完成调用：{len(executed_calls)}
当前轮次：{round_index + 1}
已有 Observation：
{json.dumps(observations[-8:], ensure_ascii=False)}

只输出一个JSON对象，不要Markdown：
{{"calls":[{{"tool":"工具名","arguments":{{}}}}],"done":false}}

说明：
- calls 可包含多个互不依赖的工具，以便并发执行。
- 仍需根据结果补充工具时 done=false。
- 信息已经足够生成最终回答时 calls=[] 且 done=true。
"""
        response = await self.llm.ainvoke(prompt)
        content = self._json_content(response.content)
        calls = content.get("calls") or []
        if not isinstance(calls, list):
            raise TypeError("Agent calls must be a list")
        return calls, bool(content.get("done"))

    @staticmethod
    def _json_content(content: Any) -> dict[str, Any]:
        text = str(content or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end <= start:
                raise
            value = json.loads(text[start:end + 1])
        if not isinstance(value, dict):
            raise TypeError("Agent response must be a JSON object")
        return value

    @staticmethod
    def _finalize_agent_context(
        citations_by_chunk: dict[str, Citation],
        tool_results: list[ToolResult],
    ) -> tuple[list[Citation], list[ToolResult]]:
        citations = [
            citation.model_copy(update={"index": index})
            for index, citation in enumerate(citations_by_chunk.values(), start=1)
        ]
        return citations, tool_results

    async def _search_with_timeout(self, client_id: str, query: str) -> list[Citation]:
        try:
            return await asyncio.wait_for(
                self.knowledge.search(client_id, query),
                timeout=self.settings.rag_timeout_seconds,
            )
        except (TimeoutError, OSError):
            return []

    async def _tools_with_timeout(self, extraction: dict, query: str) -> list[ToolResult]:
        try:
            return await asyncio.wait_for(
                mcp_travel_service.collect(extraction, query),
                timeout=self.settings.mcp_timeout_seconds,
            )
        except TimeoutError:
            return [
                ToolResult(
                    name="realtime-tools",
                    success=False,
                    content="实时工具响应超时，本次方案未使用实时数据。",
                )
            ]

    async def _complete_answer(self, query: str, prepared: PreparedChat) -> str:
        extraction = prepared.extraction
        citations = prepared.citations
        tool_results = prepared.tools

        if self._is_complete_realtime_request(extraction):
            answer = self._realtime_answer(tool_results)
        else:
            deep_analysis = await self._deep_analysis(
                query,
                extraction,
                tool_results,
                prepared.scenario_type,
            )
            answer = await self._generate_answer(
                query,
                prepared.history,
                extraction,
                citations,
                tool_results,
                deep_analysis,
                prepared.memory_context,
            )
        return self._ensure_citations(answer, citations)

    def _save_response(self, prepared: PreparedChat, answer: str) -> TravelResponse:
        conversation = self.conversations.get(prepared.conversation_id)
        if conversation is None:
            raise ValueError("会话不存在")
        self.conversations.add_message(conversation, "assistant", answer)
        return TravelResponse(
            conversation_id=prepared.conversation_id,
            answer=answer,
            citations=prepared.citations,
            tools=prepared.tools,
            scenario_type=prepared.scenario_type,
            retrieved_chunks=len(prepared.citations),
            trip_summary=TripSummary(
                destination=prepared.extraction.get("destination") or None,
                origin=prepared.extraction.get("origin") or None,
                travel_date=prepared.extraction.get("travel_date") or None,
                travel_days=prepared.extraction.get("travel_days") or None,
                travelers=prepared.extraction.get("travelers") or None,
                budget=prepared.extraction.get("budget") or None,
                preferences=prepared.extraction.get("preferences") or [],
            ),
        )

    async def _extract(self, query: str) -> dict:
        fallback = self._fallback_extract(query)
        if not self.llm or self._can_use_fallback_extraction(fallback):
            return fallback

        prompt = f"""今天是 {datetime.now():%Y-%m-%d}。从旅行需求中提取信息。
只输出JSON，不要Markdown：
{{"intent":"casual|travel_plan|travel_question","destination":"多个城市用逗号分隔","origin":"","travel_days":0,"travelers":0,"budget":0,"travel_date":"YYYY-MM-DD","preferences":[],"has_special_needs":false,"needs_rag":true,"tool_intents":["train"]}}
规则：
- 闲聊、问候、与旅行无关的问题：intent=casual, needs_rag=false, tool_intents=[]。
- 只有用户明确需要查询火车、高铁、动车或 12306 时才填 train。
- 查高铁/火车必须同时有 origin、destination；缺少日期时仍填 train，系统会使用当天日期。
        用户需求：{query}"""
        try:
            response = await asyncio.wait_for(
                self.llm.ainvoke(prompt),
                timeout=self.settings.llm_extraction_timeout_seconds,
            )
            content = str(response.content).strip().removeprefix("```json").removesuffix("```").strip()
            extracted = json.loads(content)
            return {**fallback, **extracted}
        except Exception:
            return fallback

    def _can_use_fallback_extraction(self, fallback: dict) -> bool:
        if fallback.get("intent") == "casual":
            return True
        return self._is_complete_realtime_request(fallback)

    def _fallback_extract(self, query: str) -> dict:
        days_match = re.search(r"(\d+|[一二三四五六七八九十]+)\s*天", query)
        budget_match = re.search(r"预算\s*(\d+(?:\.\d+)?)", query)
        travelers_match = re.search(r"(\d+)\s*(?:人|位)(?:出行|旅行|旅游|同行)?", query)
        date_match = re.search(r"(20\d{2})[-年/](\d{1,2})[-月/](\d{1,2})", query)
        month_day_match = re.search(r"(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*(?:日|号)?", query)
        route_query = re.sub(
            r"^(?:我想|我要|我准备|帮我|请|麻烦)?"
            r"(?:查询|查(?:一下)?|看看)?(?:今天|明天|后天)?\s*",
            "",
            query,
        )
        route_match = re.search(
            r"(?:从\s*)?([^，,。\s]+?)(?:出发)?(?:去|到)([^，,。\s]+?)"
            r"(?=(?:，|,|。|\s|帮|查|玩|旅游|旅行|出行|安排|的|12306|车票|高铁|动车|$))",
            route_query,
        )
        current_location_match = re.search(
            r"(?:我(?:现在|目前)?在|人在|现在在|目前在|当前(?:位置)?(?:在|是))\s*"
            r"([^，,。\s]+?)(?:，|,|。|\s|出发|$)",
            query,
        )
        destination_match = re.search(
            r"(?:想去|去|到)([^，,。\s]+?)"
            r"(?=(?:玩|旅游|旅行|出行|安排|的车|的高|的动|12306|车票|高铁|动车|$))",
            query,
        )
        weather_match = re.search(
            r"(?:请|帮我|麻烦)?(?:查(?:一下)?|查询|看看)?\s*"
            r"([^\s，,。！？?]{2,12}?)(?:(?:今天|明天|后天|未来\d+天)(?:的)?)?"
            r"(?:的)?(?:天气|气温)",
            query,
        )

        travel_date = ""
        if date_match:
            travel_date = f"{date_match.group(1)}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"
        elif month_day_match:
            today = datetime.now()
            year = today.year
            month = int(month_day_match.group(1))
            day = int(month_day_match.group(2))
            try:
                parsed_date = datetime(year, month, day)
                if parsed_date.date() < today.date():
                    parsed_date = parsed_date.replace(year=year + 1)
                travel_date = parsed_date.strftime("%Y-%m-%d")
            except ValueError:
                travel_date = ""
        else:
            relative_days = next(
                (days for keyword, days in (("后天", 2), ("明天", 1), ("今天", 0)) if keyword in query),
                None,
            )
            if relative_days is not None:
                travel_date = (datetime.now() + timedelta(days=relative_days)).strftime("%Y-%m-%d")

        destination = ""
        origin = ""
        if route_match:
            origin = route_match.group(1)
            destination = route_match.group(2)
        elif destination_match:
            destination = destination_match.group(1)
        elif weather_match:
            destination = re.sub(
                r"^(?:今天|明天|后天|未来\d+天)",
                "",
                weather_match.group(1),
            ).strip()
        if not origin and current_location_match:
            origin = current_location_match.group(1)

        tool_intents = self._fallback_tool_intents(query)
        if "train" in tool_intents and not (origin and destination):
            tool_intents.remove("train")

        return {
            "intent": self._fallback_intent(query),
            "destination": destination,
            "origin": origin,
            "travel_days": self._parse_day_count(days_match.group(1)) if days_match else 0,
            "travelers": int(travelers_match.group(1)) if travelers_match else 0,
            "budget": float(budget_match.group(1)) if budget_match else 0,
            "travel_date": travel_date,
            "preferences": [],
            "has_special_needs": any(
                word in query for word in ("老人", "儿童", "小孩", "亲子", "轮椅", "无障碍")
            ),
            "needs_rag": self._fallback_needs_rag(query),
            "tool_intents": tool_intents,
        }

    @staticmethod
    def _parse_day_count(value: str) -> int:
        if value.isdigit():
            return int(value)
        numerals = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
        if "十" not in value:
            return numerals.get(value, 0)
        tens, _, ones = value.partition("十")
        return (numerals.get(tens, 1) * 10) + numerals.get(ones, 0)

    def _fallback_intent(self, query: str) -> str:
        travel_keywords = (
            "旅行",
            "旅游",
            "行程",
            "攻略",
            "景点",
            "酒店",
            "住宿",
            "交通",
            "高铁",
            "火车",
            "航班",
            "飞机",
            "黄历",
            "吉日",
            "出行",
            "预算",
            "玩",
            "出游",
            "几点去",
            "门票",
            "开放",
            "车票",
            "12306",
            "天气",
            "气温",
            "下雨",
        )
        if not any(keyword in query for keyword in travel_keywords):
            return "casual"
        if any(keyword in query for keyword in ("几度", "天气", "几点", "门票", "开放")):
            return "travel_question"
        return "travel_plan"

    def _fallback_needs_rag(self, query: str) -> bool:
        if self._fallback_intent(query) == "casual":
            return False
        realtime_keywords = (
            "高铁",
            "火车",
            "车票",
            "12306",
        )
        planning_keywords = ("旅行", "旅游", "行程", "攻略", "景点", "酒店", "住宿", "几天", "怎么玩")
        return any(keyword in query for keyword in planning_keywords) or not any(
            keyword in query for keyword in realtime_keywords
        )

    def _fallback_tool_intents(self, query: str) -> list[str]:
        intents: list[str] = []
        if any(keyword in query for keyword in ("高铁", "火车", "车票", "动车", "12306")):
            intents.append("train")
        return intents

    def _normalize_extraction(self, query: str, extraction: dict) -> dict:
        fallback = self._fallback_extract(query)
        normalized = dict(fallback)
        for key in ("destination", "origin", "travel_date"):
            value = str(extraction.get(key) or "").strip()
            if value:
                normalized[key] = value
        for key in ("travel_days", "travelers", "budget"):
            if extraction.get(key):
                normalized[key] = extraction[key]
        if extraction.get("preferences"):
            normalized["preferences"] = extraction["preferences"]
        normalized["has_special_needs"] = bool(
            fallback.get("has_special_needs") or extraction.get("has_special_needs")
        )

        fallback_intent = str(fallback.get("intent") or "casual")
        intent = str(extraction.get("intent") or fallback_intent)
        if intent not in {"casual", "travel_plan", "travel_question"}:
            intent = fallback_intent
        if fallback_intent != "casual" and intent == "casual":
            intent = fallback_intent
        normalized["intent"] = intent

        extracted_tools = extraction.get("tool_intents") or []
        if isinstance(extracted_tools, str):
            extracted_tools = [item.strip() for item in extracted_tools.split(",") if item.strip()]
        allowed_tools = {"train"}
        normalized_tool_intents = list(
            dict.fromkeys(
                intent
                for intent in [*self._fallback_tool_intents(query), *extracted_tools]
                if intent in allowed_tools
            )
        )
        origin = str(normalized.get("origin", "")).strip()
        destination = str(normalized.get("destination", "")).strip()
        travel_days = int(normalized.get("travel_days") or 0)
        if "train" in normalized_tool_intents and not (origin and destination):
            normalized_tool_intents.remove("train")
        normalized["tool_intents"] = normalized_tool_intents
        needs_rag = extraction.get("needs_rag")
        if isinstance(needs_rag, str):
            needs_rag = needs_rag.strip().lower() in {"true", "1", "yes", "是", "需要"}
        normalized["needs_rag"] = bool(
            fallback.get("needs_rag")
            or needs_rag
            or (intent == "travel_plan" and destination and travel_days > 0)
        )
        return normalized

    def _should_search_knowledge(self, query: str, extraction: dict) -> bool:
        if extraction.get("intent") == "casual":
            return False
        return bool(extraction.get("needs_rag"))

    def _should_collect_tools(self, extraction: dict) -> bool:
        if extraction.get("intent") == "casual":
            return False
        return bool(extraction.get("tool_intents"))

    def _is_complete_realtime_request(self, extraction: dict) -> bool:
        tool_intents = set(extraction.get("tool_intents") or [])
        if tool_intents != {"train"}:
            return False
        if int(extraction.get("travel_days") or 0) > 0:
            return False

        destination = str(extraction.get("destination") or "").strip()
        origin = str(extraction.get("origin") or "").strip()
        return bool(origin and destination)

    def _scenario_type(self, query: str, extraction: dict) -> str:
        destination = str(extraction.get("destination", ""))
        separators = ("、", ",", "，", "然后", "再去", "之后去", "和")
        if any(separator in destination for separator in separators) or any(
            keyword in query for keyword in ("再去", "然后去", "途经", "多城市")
        ):
            return "multi_destination"
        if extraction.get("has_special_needs") or any(
            keyword in query for keyword in ("预算紧张", "兼顾", "多重要求")
        ):
            return "complex"
        return "simple"

    async def _deep_analysis(
        self,
        query: str,
        extraction: dict,
        tools: list[ToolResult],
        scenario_type: str,
    ) -> str:
        if scenario_type == "simple" or not self.settings.deepseek_api_key:
            return ""
        analyzer = DeepSeekR1Analyzer(
            api_key=self.settings.deepseek_api_key,
            base_url=self.settings.deepseek_base_url,
            model=self.settings.deepseek_reasoning_model,
        )
        try:
            return await asyncio.wait_for(
                analyzer.analyze(
                    query,
                    {
                        "extraction": extraction,
                        "tools": [tool.model_dump() for tool in tools],
                    },
                ),
                timeout=min(20, self.settings.llm_generation_timeout_seconds / 2),
            )
        except TimeoutError:
            return ""

    async def _stream_answer(
        self,
        query: str,
        prepared: PreparedChat,
    ) -> AsyncIterator[str]:
        if self._is_complete_realtime_request(prepared.extraction):
            yield self._realtime_answer(prepared.tools)
            return

        deep_analysis = await self._deep_analysis(
            query,
            prepared.extraction,
            prepared.tools,
            prepared.scenario_type,
        )
        if not self.llm:
            if prepared.extraction.get("intent") == "casual":
                yield "你好！我可以帮你规划旅行路线、整理行程、查询知识库资料，也可以在信息足够时调用实时工具。"
            else:
                yield self._offline_answer(query, prepared.citations, prepared.tools)
            return

        prompt = self._answer_prompt(
            query,
            prepared.history,
            prepared.extraction,
            prepared.citations,
            prepared.tools,
            deep_analysis,
            prepared.memory_context,
        )
        received_content = False
        try:
            async with asyncio.timeout(self.settings.llm_generation_timeout_seconds):
                async for response in self.llm.astream(prompt):
                    content = response.content
                    if not isinstance(content, str):
                        content = str(content or "")
                    if content:
                        received_content = True
                        yield content
        except TimeoutError:
            if received_content:
                yield "\n\n> 生成时间已达到上限，以上内容可能不完整。"
            else:
                yield self._offline_answer(
                    query,
                    prepared.citations,
                    prepared.tools,
                    error="模型响应超时",
                )
        except Exception:
            if received_content:
                yield "\n\n> 模型连接中断，以上为已经生成的内容。"
            else:
                yield self._offline_answer(
                    query,
                    prepared.citations,
                    prepared.tools,
                    error="模型服务暂时不可用",
                )

    async def _generate_answer(
        self,
        query: str,
        history,
        extraction: dict,
        citations: list[Citation],
        tools: list[ToolResult],
        deep_analysis: str,
        memory_context: str,
    ) -> str:
        if not self.llm:
            if extraction.get("intent") == "casual":
                return "你好！我可以帮你规划旅行路线、整理行程、查询知识库资料，也可以在信息足够时调用实时工具。"
            return self._offline_answer(query, citations, tools)

        prompt = self._answer_prompt(
            query,
            history,
            extraction,
            citations,
            tools,
            deep_analysis,
            memory_context,
        )
        try:
            response = await asyncio.wait_for(
                self.llm.ainvoke(prompt),
                timeout=self.settings.llm_generation_timeout_seconds,
            )
            return str(response.content).strip()
        except TimeoutError:
            return self._offline_answer(query, citations, tools, error="模型响应超时")
        except Exception:
            return self._offline_answer(query, citations, tools, error="模型服务暂时不可用")

    def _answer_prompt(
        self,
        query: str,
        history,
        extraction: dict,
        citations: list[Citation],
        tools: list[ToolResult],
        deep_analysis: str,
        memory_context: str,
    ) -> str:
        source_context = "\n\n".join(
            f"[来源{item.index}] {item.source}"
            f"{f' 第{item.page}页' if item.page else ''}\n{item.excerpt}"
            for item in citations
        ) or "没有检索到本地知识库资料。"
        tool_context = "\n\n".join(
            f"[{tool.name}] {'成功' if tool.success else '失败'}\n{tool.content[:2500]}"
            for tool in tools
        ) or "本次没有调用实时工具。"
        history_context = "\n".join(
            f"{message.role}: {message.content[:1000]}" for message in history[:-1]
        )
        return f"""你是专业旅行规划助手。请使用中文回答，事实必须来自资料或工具结果。
如果使用知识库内容，在对应句末标注 [来源N]；工具失败时明确说明，禁止虚构实时数据。
输出应包括：需求理解、建议行程、交通、住宿、美食或景点、预算提示、风险与备选方案。信息不足时先给可执行方案并指出待确认项。

历史对话：
{history_context or '无'}

长期记忆：
{memory_context}

结构化需求：
{json.dumps(extraction, ensure_ascii=False)}

用户本轮问题：
{query}

知识库资料：
{source_context}

实时工具结果：
{tool_context}

复杂分析：
{deep_analysis or '无'}
"""

    def _realtime_answer(self, tools: list[ToolResult]) -> str:
        lines = ["### 实时查询结果"]
        successful_tools = [tool for tool in tools if tool.success]
        failed_tools = [tool for tool in tools if not tool.success]

        for tool in successful_tools:
            if tool.name == "get-tickets":
                lines.extend(["\n#### 12306 实时车次", tool.content.strip()])
            else:
                lines.extend([f"\n#### {tool.name}", tool.content.strip()])

        for tool in failed_tools:
            error = tool.content.strip()
            parsed_error = None
            try:
                parsed_error = json.loads(error).get("error")
            except (AttributeError, TypeError, json.JSONDecodeError):
                pass
            lines.extend([f"\n#### {tool.name} 查询失败", str(parsed_error or error)])

        if not tools:
            lines.append("实时工具未返回结果，请确认城市、出发地、目的地和日期是否完整。")
        lines.append("\n实时信息可能变化，购票和出发前请再通过官方渠道确认。")
        return "\n".join(lines)

    def _offline_answer(
        self,
        query: str,
        citations: list[Citation],
        tools: list[ToolResult],
        error: str | None = None,
    ) -> str:
        lines = [f"已收到旅行需求：{query}"]
        if error:
            lines.append(f"模型服务暂时不可用：{error}")
        if citations:
            lines.append("\n根据知识库，可参考：")
            lines.extend(
                f"- {item.excerpt[:160]} [来源{item.index}]" for item in citations[:3]
            )
        successful_tools = [tool for tool in tools if tool.success]
        if successful_tools:
            lines.append("\n### 实时查询结果")
            for tool in successful_tools:
                content = tool.content.strip()
                if len(content) > 3000:
                    content = content[:3000].rstrip() + "\n（结果较长，已截取前 3000 字）"
                lines.append(f"\n**{tool.name}**\n{content}")
        if not citations and not successful_tools:
            lines.append("当前没有可用知识库或实时数据，请检查模型和MCP配置。")
        return "\n".join(lines)

    def _ensure_citations(self, answer: str, citations: list[Citation]) -> str:
        if not citations:
            return answer
        references = ["\n\n### 参考资料"]
        for citation in citations:
            page = f"，第{citation.page}页" if citation.page else ""
            references.append(f"- [来源{citation.index}] {citation.source}{page}")
        return answer.rstrip() + "\n".join(references)
