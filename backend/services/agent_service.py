from datetime import datetime
import json
import re

from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from aggentic_RAG.travel_agent.tools.r1_tool import DeepSeekR1Analyzer

from ..config import Settings, get_settings
from ..repositories.conversations import ConversationRepository
from ..schemas import Citation, ToolResult, TravelRequest, TravelResponse
from .knowledge_service import KnowledgeService
from .mcp_travel_service import mcp_travel_service


class TravelAgentService:
    def __init__(self, database: Session, settings: Settings | None = None):
        self.database = database
        self.settings = settings or get_settings()
        self.conversations = ConversationRepository(database)
        self.knowledge = KnowledgeService(database, self.settings)
        self.llm = None
        if self.settings.dashscope_api_key:
            self.llm = ChatOpenAI(
                model=self.settings.qwen_model,
                api_key=self.settings.dashscope_api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                temperature=0.4,
            )

    async def chat(self, request: TravelRequest) -> TravelResponse:
        conversation = None
        if request.conversation_id:
            conversation = self.conversations.get(request.conversation_id, request.client_id)
            if conversation is None:
                raise ValueError("会话不存在或不属于当前客户端")
        else:
            conversation = self.conversations.create(request.client_id)

        self.conversations.add_message(conversation, "user", request.query)
        history = self.conversations.recent_messages(conversation.id, limit=12)
        extraction = await self._extract(request.query)
        scenario_type = self._scenario_type(request.query, extraction)
        citations = await self.knowledge.search(request.query)
        tool_results = await mcp_travel_service.collect(extraction, request.query)
        deep_analysis = await self._deep_analysis(
            request.query,
            extraction,
            tool_results,
            scenario_type,
        )
        answer = await self._generate_answer(
            request.query,
            history,
            extraction,
            citations,
            tool_results,
            deep_analysis,
        )
        answer = self._ensure_citations(answer, citations)
        self.conversations.add_message(conversation, "assistant", answer)

        return TravelResponse(
            conversation_id=conversation.id,
            answer=answer,
            citations=citations,
            tools=tool_results,
            scenario_type=scenario_type,
            retrieved_chunks=len(citations),
        )

    async def _extract(self, query: str) -> dict:
        fallback = self._fallback_extract(query)
        if not self.llm:
            return fallback

        prompt = f"""今天是 {datetime.now():%Y-%m-%d}。从旅行需求中提取信息。
只输出JSON，不要Markdown：
{{"destination":"多个城市用逗号分隔","origin":"","travel_days":0,"budget":0,"travel_date":"YYYY-MM-DD","preferences":[],"has_special_needs":false}}
用户需求：{query}"""
        try:
            response = await self.llm.ainvoke(prompt)
            content = str(response.content).strip().removeprefix("```json").removesuffix("```").strip()
            extracted = json.loads(content)
            return {**fallback, **extracted}
        except Exception:
            return fallback

    def _fallback_extract(self, query: str) -> dict:
        days_match = re.search(r"(\d+)\s*天", query)
        budget_match = re.search(r"预算\s*(\d+(?:\.\d+)?)", query)
        date_match = re.search(r"(20\d{2})[-年/](\d{1,2})[-月/](\d{1,2})", query)
        route_match = re.search(r"从([^，,。\s]+?)(?:出发)?(?:去|到)([^，,。\s]+)", query)

        travel_date = ""
        if date_match:
            travel_date = f"{date_match.group(1)}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"
        return {
            "destination": route_match.group(2) if route_match else "",
            "origin": route_match.group(1) if route_match else "",
            "travel_days": int(days_match.group(1)) if days_match else 0,
            "budget": float(budget_match.group(1)) if budget_match else 0,
            "travel_date": travel_date,
            "preferences": [],
            "has_special_needs": any(
                word in query for word in ("老人", "儿童", "小孩", "亲子", "轮椅", "无障碍")
            ),
        }

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
        analyzer = DeepSeekR1Analyzer(api_key=self.settings.deepseek_api_key)
        return await analyzer.analyze(
            query,
            {
                "extraction": extraction,
                "tools": [tool.model_dump() for tool in tools],
            },
        )

    async def _generate_answer(
        self,
        query: str,
        history,
        extraction: dict,
        citations: list[Citation],
        tools: list[ToolResult],
        deep_analysis: str,
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

        if not self.llm:
            return self._offline_answer(query, citations, tools)

        prompt = f"""你是专业旅行规划助手。请使用中文回答，事实必须来自资料或工具结果。
如果使用知识库内容，在对应句末标注 [来源N]；工具失败时明确说明，禁止虚构实时数据。
输出应包括：需求理解、建议行程、交通、住宿、美食或景点、预算提示、风险与备选方案。信息不足时先给可执行方案并指出待确认项。

历史对话：
{history_context or '无'}

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
        try:
            response = await self.llm.ainvoke(prompt)
            return str(response.content).strip()
        except Exception as exc:
            return self._offline_answer(query, citations, tools, error=str(exc))

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
            lines.append("\n实时工具已经返回结果，恢复模型服务后可生成完整行程。")
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
