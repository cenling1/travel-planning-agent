from dataclasses import dataclass, field
from typing import Any

from ..schemas import Citation, ToolResult
from .knowledge_service import KnowledgeService
from .mcp_travel_service import MCPTravelService, mcp_travel_service


@dataclass(frozen=True)
class AgentToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]

    def as_prompt_value(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


AGENT_TOOL_DEFINITIONS = (
    AgentToolDefinition(
        name="knowledge_search",
        description="检索用户自己的旅游知识库，适合查询攻略、景点、美食、住宿和注意事项。",
        parameters={
            "query": "检索问题或关键词",
            "top_k": "可选，返回结果数量，1到8",
        },
    ),
    AgentToolDefinition(
        name="train_query",
        description="查询12306实时车次。内部会自动将城市转换为站点代码；缺少日期时使用当天。",
        parameters={
            "origin": "出发城市",
            "destination": "目的城市",
            "date": "可选，YYYY-MM-DD",
            "train_type": "可选，高铁/G或动车/D",
        },
    ),
)

AGENT_TOOL_NAMES = {tool.name for tool in AGENT_TOOL_DEFINITIONS}


@dataclass
class AgentToolOutcome:
    observation: str
    citations: list[Citation] = field(default_factory=list)
    result: ToolResult | None = None


def tool_catalog() -> list[dict[str, Any]]:
    return [tool.as_prompt_value() for tool in AGENT_TOOL_DEFINITIONS]


class TravelToolExecutor:
    def __init__(
        self,
        knowledge: KnowledgeService,
        owner_id: str,
        default_query: str,
        mcp_service: MCPTravelService | None = None,
    ):
        self.knowledge = knowledge
        self.owner_id = owner_id
        self.default_query = default_query
        self.mcp = mcp_service or mcp_travel_service

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> AgentToolOutcome:
        handler = getattr(self, f"_execute_{tool_name}", None)
        if handler is None:
            result = ToolResult(
                name=tool_name,
                success=False,
                content=f"未知工具: {tool_name}",
            )
            return AgentToolOutcome(observation=result.content, result=result)
        try:
            return await handler(arguments)
        except Exception as exc:
            result = ToolResult(
                name=tool_name,
                success=False,
                content=f"工具执行失败: {exc}",
            )
            return AgentToolOutcome(observation=result.content, result=result)

    async def _execute_knowledge_search(
        self,
        arguments: dict[str, Any],
    ) -> AgentToolOutcome:
        query = self._text(arguments, "query", default=self.default_query)
        top_k = max(1, min(8, int(arguments.get("top_k") or 5)))
        citations = await self.knowledge.search(self.owner_id, query, top_k=top_k)
        if not citations:
            return AgentToolOutcome(observation="知识库没有检索到相关资料。")
        observation = "\n\n".join(
            f"[来源{citation.index}] {citation.source}\n{citation.excerpt[:600]}"
            for citation in citations
        )
        return AgentToolOutcome(observation=observation, citations=citations)

    async def _execute_train_query(self, arguments: dict[str, Any]) -> AgentToolOutcome:
        origin = self._text(arguments, "origin")
        destination = self._text(arguments, "destination")
        date = self._text(arguments, "date", default="")
        train_type = self._text(arguments, "train_type", default="").upper()
        train_filter_flags = ""
        if train_type in {"G", "高铁"}:
            train_filter_flags = "G"
        elif train_type in {"D", "动车"}:
            train_filter_flags = "D"
        result = await self.mcp.query_train(
            origin,
            destination,
            date,
            train_filter_flags=train_filter_flags,
        )
        return self._tool_outcome(result)

    @staticmethod
    def _text(
        arguments: dict[str, Any],
        key: str,
        default: str | None = None,
    ) -> str:
        value = str(arguments.get(key) or default or "").strip()
        if not value and default is None:
            raise ValueError(f"缺少参数 {key}")
        return value

    @staticmethod
    def _tool_outcome(result: ToolResult) -> AgentToolOutcome:
        status = "成功" if result.success else "失败"
        return AgentToolOutcome(
            observation=f"{result.name} {status}\n{result.content[:4000]}",
            result=result,
        )
