import asyncio
from datetime import datetime
import json
import time
from typing import Any

from ..integrations.mcp import MCPToolManager
from ..schemas import ToolResult


def _json_value(value: str) -> Any:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


def _is_error_content(content: str) -> bool:
    parsed = _json_value(content)
    if isinstance(parsed, dict) and parsed.get("error"):
        return True
    if not isinstance(parsed, str):
        return False
    normalized = parsed.strip().lower()
    return normalized.startswith(("error:", "工具调用失败:")) or "station not found" in normalized


class MCPTravelService:
    def __init__(self):
        self.manager = MCPToolManager()
        self._initialized = False
        self._initialize_lock = asyncio.Lock()

    async def initialize(self) -> None:
        if self._initialized:
            return
        async with self._initialize_lock:
            if not self._initialized:
                await self.manager.initialize()
                self._initialized = True

    async def call(self, server: str, tool: str, **arguments) -> ToolResult:
        started = time.perf_counter()
        try:
            await self.initialize()
            content = await asyncio.wait_for(
                self.manager.call_tool(server, tool, **arguments),
                timeout=25,
            )
            return ToolResult(
                name=tool,
                success=not _is_error_content(content),
                content=content,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        except Exception as exc:
            return ToolResult(
                name=tool,
                success=False,
                content=f"工具调用失败: {exc}",
                latency_ms=int((time.perf_counter() - started) * 1000),
            )

    async def collect(self, extraction: dict, query: str) -> list[ToolResult]:
        destinations = [
            city.strip()
            for city in str(extraction.get("destination", "")).replace("，", ",").split(",")
            if city.strip()
        ]
        origin = str(extraction.get("origin", "")).strip()
        travel_date = str(extraction.get("travel_date", "")).strip()
        travel_days = int(extraction.get("travel_days") or 0)
        tool_intents = set(extraction.get("tool_intents") or [])

        may_call_tools = (
            destinations
            and tool_intents.intersection({"weather", "attractions", "hotel"})
        ) or (
            origin
            and destinations
            and (
                "train" in tool_intents
                or (travel_date and "flight" in tool_intents)
            )
        ) or (travel_date and "calendar" in tool_intents)
        if not may_call_tools:
            return []

        try:
            await self.initialize()
        except (OSError, json.JSONDecodeError):
            return [
                ToolResult(
                    name="realtime-tools",
                    success=False,
                    content="实时工具尚未配置，当前无法查询实时数据。",
                )
            ]

        tasks = []
        for city in destinations[:2]:
            if "Gaode Server" in self.manager.servers:
                if "weather" in tool_intents:
                    tasks.append(self.call("Gaode Server", "maps_weather", city=city))
                if "attractions" in tool_intents:
                    tasks.append(
                        self.call(
                            "Gaode Server",
                            "maps_text_search",
                            keywords=f"{city} 景点",
                            city=city,
                        )
                    )
                if "hotel" in tool_intents and (
                    travel_days > 1 or any(word in query for word in ("酒店", "住宿", "民宿"))
                ):
                    tasks.append(
                        self.call(
                            "Gaode Server",
                            "maps_text_search",
                            keywords=f"{city} 酒店",
                            city=city,
                        )
                    )

        if (
            "train" in tool_intents
            and origin
            and destinations
            and "12306 Server" in self.manager.servers
        ):
            train_filter_flags = ""
            if "高铁" in query:
                train_filter_flags = "G"
            elif "动车" in query:
                train_filter_flags = "D"
            tasks.append(
                self.query_train(
                    origin,
                    destinations[0],
                    travel_date,
                    train_filter_flags=train_filter_flags,
                )
            )

        if travel_date and "calendar" in tool_intents:
            if "bazi Server" in self.manager.servers:
                tasks.append(
                    self.call(
                        "bazi Server",
                        "getChineseCalendar",
                        solarDatetime=f"{travel_date}T12:00:00+08:00",
                    )
                )

        if destinations and travel_date and "flight" in tool_intents:
            if "flight Server" in self.manager.servers:
                tasks.append(
                    self.call(
                        "flight Server",
                        "searchFlightsByDepArr",
                        dep=origin,
                        arr=destinations[0],
                        date=travel_date,
                    )
                )

        if not tasks:
            return []
        return list(await asyncio.gather(*tasks))

    async def query_train(
        self,
        origin: str,
        destination: str,
        date: str,
        train_filter_flags: str = "",
    ) -> ToolResult:
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        try:
            date_value = datetime.strptime(date, "%Y-%m-%d")
            if date_value.year < datetime.now().year:
                date = date_value.replace(year=datetime.now().year).strftime("%Y-%m-%d")
        except ValueError:
            pass

        origin_code = await self._station_code(origin)
        destination_code = await self._station_code(destination)
        return await self.call(
            "12306 Server",
            "get-tickets",
            fromStation=origin_code or origin,
            toStation=destination_code or destination,
            date=date,
            trainFilterFlags=train_filter_flags,
            sortFlag="duration",
            limitedNum=10,
            format="text",
        )

    async def _station_code(self, city: str) -> str | None:
        result = await self.call(
            "12306 Server",
            "get-stations-code-in-city",
            city=city,
        )
        if not result.success:
            return None
        data = _json_value(result.content)
        if isinstance(data, dict):
            for key in ("data", "result", "return"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break
        if not isinstance(data, list):
            return None

        stations = sorted(
            data,
            key=lambda item: (
                item.get("station_name") != city,
                city not in item.get("station_name", ""),
            ),
        )
        for station in stations:
            code = station.get("station_code") or station.get("code") or station.get("telecode")
            if code:
                return str(code)
        return None

    async def health(self) -> dict[str, bool]:
        try:
            await self.initialize()
        except (OSError, json.JSONDecodeError):
            return {}
        return {
            name: bool(connection.session_id)
            for name, connection in self.manager.servers.items()
        }


mcp_travel_service = MCPTravelService()
