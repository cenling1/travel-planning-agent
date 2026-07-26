"""
MCP工具封装 - 直接使用 httpx 实现 Streamable HTTP 协议
兼容 ModelScope 等平台的 MCP 服务器
"""
import json
import os
import httpx
from typing import Optional, Dict, List

from ..config import get_settings

MCP_INITIALIZE_TIMEOUT = 10.0

# 绕过代理直连ModelScope
os.environ['NO_PROXY'] = os.environ.get('NO_PROXY', '') + ',modelscope.net,api-inference.modelscope.net'


def _safe_error_message(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        response = error.response
        return f"HTTP {response.status_code} {response.reason_phrase}"
    return str(error)


class MCPServerConnection:
    """单个 MCP 服务器的 Streamable HTTP 连接"""

    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url.rstrip('/')
        self.session_id: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._request_id = 0

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=60.0,
                headers={
                    'Accept': 'application/json, text/event-stream',
                    'Content-Type': 'application/json',
                }
            )
        return self._client

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def initialize(self) -> bool:
        """初始化连接，获取 session ID"""
        self.session_id = None
        try:
            client = await self._get_client()
            resp = await client.post(
                self.url,
                timeout=MCP_INITIALIZE_TIMEOUT,
                json={
                    'jsonrpc': '2.0',
                    'id': self._next_id(),
                    'method': 'initialize',
                    'params': {
                        'protocolVersion': '2025-03-26',
                        'capabilities': {},
                        'clientInfo': {'name': 'travel-agent', 'version': '1.0'}
                    }
                }
            )

            if resp.status_code != 200:
                return False

            self.session_id = resp.headers.get('mcp-session-id', '')
            if not self.session_id:
                return False

            # Send initialized notification
            await client.post(
                self.url,
                timeout=MCP_INITIALIZE_TIMEOUT,
                json={'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                headers={'Mcp-Session-Id': self.session_id}
            )

            return True
        except Exception:
            return False

    async def call_tool(self, tool_name: str, arguments: dict = None) -> str:
        """调用 MCP 工具"""
        if not self.session_id:
            if not await self.initialize():
                raise ConnectionError(f"服务器 {self.name} 未连接")

        client = await self._get_client()
        resp = await client.post(
            self.url,
            json={
                'jsonrpc': '2.0',
                'id': self._next_id(),
                'method': 'tools/call',
                'params': {
                    'name': tool_name,
                    'arguments': arguments or {}
                }
            },
            headers={'Mcp-Session-Id': self.session_id}
        )
        resp.raise_for_status()

        data = resp.json()
        if data.get('error'):
            raise RuntimeError(json.dumps(data['error'], ensure_ascii=False))

        result = data.get('result', {})
        content = result.get('content', [])

        texts = []
        for item in content:
            if isinstance(item, dict) and item.get('type') == 'text':
                texts.append(item.get('text', ''))
            elif isinstance(item, dict) and 'text' in item:
                texts.append(item['text'])
            elif isinstance(item, str):
                texts.append(item)

        text = '\n'.join(texts) if texts else json.dumps(result, ensure_ascii=False)
        if result.get('isError'):
            raise RuntimeError(text or f"工具 {tool_name} 调用失败")
        return text

    async def list_tools(self) -> List[dict]:
        """列出服务器可用工具"""
        if not self.session_id:
            if not await self.initialize():
                return []

        try:
            client = await self._get_client()
            resp = await client.post(
                self.url,
                json={
                    'jsonrpc': '2.0',
                    'id': self._next_id(),
                    'method': 'tools/list',
                    'params': {}
                },
                headers={'Mcp-Session-Id': self.session_id}
            )

            if resp.status_code == 200:
                data = resp.json()
                return data.get('result', {}).get('tools', [])
            return []
        except Exception:
            return []

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


class MCPToolManager:
    """MCP工具管理器 - 管理所有MCP服务器连接"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or str(get_settings().mcp_config_path)
        self.servers: Dict[str, MCPServerConnection] = {}

    async def initialize(self):
        """读取 MCP 配置；各服务器在首次工具调用时再建立连接。"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"MCP配置文件不存在: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        for server_conf in config.get("mcp_servers", []):
            name = server_conf.get("name")
            url = server_conf.get("url")

            if not url:
                continue

            conn = MCPServerConnection(name, url)
            self.servers[name] = conn

    async def call_tool(self, server_name: str, tool_name: str, max_retries: int = 2, **kwargs) -> str:
        """
        调用MCP工具，带重试机制
        """
        if server_name not in self.servers:
            return json.dumps({
                "error": f"MCP服务器 {server_name} 未连接",
                "available_servers": list(self.servers.keys())
            }, ensure_ascii=False)

        import asyncio
        last_error = None
        attempts_made = 0

        for attempt in range(max_retries + 1):
            attempts_made = attempt + 1
            try:
                if attempt > 0:
                    await asyncio.sleep(1 * attempt)

                return await self.servers[server_name].call_tool(tool_name, kwargs)

            except Exception as e:
                last_error = e
                server = self.servers[server_name]
                server.session_id = None
                is_retryable = isinstance(
                    e,
                    (ConnectionError, httpx.TimeoutException, httpx.TransportError),
                )
                if isinstance(e, httpx.HTTPStatusError):
                    status_code = e.response.status_code
                    is_retryable = status_code in {401, 408, 409, 429} or status_code >= 500
                if not is_retryable or attempt >= max_retries:
                    break

        return json.dumps({
            "error": f"工具调用失败: {_safe_error_message(last_error)}",
            "server": server_name,
            "tool": tool_name,
            "attempts": attempts_made,
        }, ensure_ascii=False)

    async def list_tools(self, server_name: str) -> List[dict]:
        """列出指定服务器的可用工具"""
        if server_name not in self.servers:
            return []
        return await self.servers[server_name].list_tools()

    async def cleanup(self):
        """清理资源"""
        for conn in self.servers.values():
            await conn.close()
        self.servers.clear()
