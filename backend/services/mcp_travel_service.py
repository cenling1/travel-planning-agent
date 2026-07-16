import asyncio
from datetime import datetime
import json
import time
from typing import Any

from aggentic_RAG.travel_agent.tools.mcp_tools import MCPToolManager

from ..schemas import ToolResult


def _json_value(value: str) -> Any:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


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
        await self.initialize()
        started = time.perf_counter()
        try:
            content = await asyncio.wait_for(
                self.manager.call_tool(server, tool, **arguments),
                timeout=25,
            )
            parsed = _json_value(content)
            success = not (isinstance(parsed, dict) and parsed.get("error"))
            return ToolResult(
                name=tool,
                success=success,
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
        await self.initialize()
        destinations = [
            city.strip()
            for city in str(extraction.get("destination", "")).replace("，", ",").split(",")
            if city.strip()
        ]
        origin = str(extraction.get("origin", "")).strip()
        travel_date = str(extraction.get("travel_date", "")).strip()
        travel_days = int(extraction.get("travel_days") or 0)

        tasks = []
        for city in destinations[:2]:
            if "Gaode Server" in self.manager.servers:
                tasks.append(self.call("Gaode Server", "maps_weather", city=city))
                tasks.append(
                    self.call(
                        "Gaode Server",
                        "maps_text_search",
                        keywords=f"{city} 景点",
                        city=city,
                    )
                )
                if travel_days > 1 or any(word in query for word in ("酒店", "住宿", "民宿")):
                    tasks.append(
                        self.call(
                            "Gaode Server",
                            "maps_text_search",
                            keywords=f"{city} 酒店",
                            city=city,
                        )
                    )

        if origin and destinations and travel_date and "12306 Server" in self.manager.servers:
            tasks.append(self.query_train(origin, destinations[0], travel_date))

        if travel_date and any(word in query for word in ("黄历", "吉日", "宜出行")):
            if "bazi Server" in self.manager.servers:
                tasks.append(
                    self.call(
                        "bazi Server",
                        "getChineseCalendar",
                        solarDatetime=f"{travel_date}T12:00:00+08:00",
                    )
                )

        if destinations and travel_date and any(word in query for word in ("飞机", "航班")):
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

    async def query_train(self, origin: str, destination: str, date: str) -> ToolResult:
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
        await self.initialize()
        return {
            name: bool(connection.session_id)
            for name, connection in self.manager.servers.items()
        }


mcp_travel_service = MCPTravelService()
