# 智能旅游规划助手

一个基于 Streamlit、LangChain ReAct、Qwen、DeepSeek R1、持久化 RAG 和 MCP 工具的旅游规划应用。用户可以描述出发地、目的地、日期、预算和偏好，系统会判断场景复杂度、调用知识库与外部工具，并生成中文旅行方案。

## 核心功能

- 使用 Qwen `qwen-plus` 提取目的地、日期、预算、天数和偏好
- 识别简单、复杂和多目的地旅行场景
- 使用 LangChain ReAct Agent 动态选择工具
- 复杂场景通过 DeepSeek `deepseek-reasoner` 分析路线、预算和风险
- 通过 MCP Streamable HTTP 调用 12306、高德地图、黄历和航班服务
- 支持 TXT、Markdown、PDF、CSV 文档导入
- 使用 DashScope Embedding 和 ChromaDB 持久化旅游知识库
- 应用重启后自动加载已有知识库

## 执行流程

```text
用户输入
   |
   v
Qwen 需求预分析
   |
   +-- simple ------------> ReAct Agent
   +-- complex -----------> DeepSeek R1 + ReAct Agent
   `-- multi_destination -> DeepSeek R1 + ReAct Agent
                                  |
                                  +-- 持久化 RAG
                                  +-- 12306 MCP
                                  +-- 高德地图 MCP
                                  +-- 黄历 MCP
                                  `-- 航班 MCP
```

根目录的 `app.py` 是唯一应用入口。Agent 的最大步骤数由侧边栏滑块控制。

## 工具能力

| 工具 | 用途 |
| --- | --- |
| `rag_search` | 检索持久化旅游知识库 |
| `train_query` | 查询站点、火车票，并尝试补充自驾信息 |
| `gaode_poi_search` | 搜索景点、餐厅等 POI |
| `gaode_hotel_search` | 搜索酒店和民宿 |
| `gaode_weather` | 查询城市天气 |
| `gaode_geo` | 地址转经纬度 |
| `gaode_driving` | 查询驾车路线 |
| `lucky_day` | 查询黄历宜忌 |
| `flight_query` | 查询航班信息 |
| `r1_analysis` | 复杂路线、预算和风险分析 |

外部工具是否可用取决于 MCP URL、服务状态和第三方接口能力。单个工具失败时，Agent 会使用已有信息继续生成结果。

## 项目结构

```text
travel-planning-agent/
|-- app.py                              # Streamlit 主入口
|-- README.md
|-- LICENSE
`-- aggentic_RAG/
    |-- requirements.txt                # 唯一依赖清单
    |-- setup.py                        # 从 requirements.txt 读取依赖
    |-- data/
    |   |-- travel_docs/                # 示例文档
    |   `-- travel_vectordb/            # 持久化 Chroma 数据库
    `-- travel_agent/
        |-- config/
        |   |-- settings.py             # 模型、RAG 和 MCP 配置
        |   |-- prompts.py              # 独立 R1 工具 Prompt
        |   `-- servers_config.json     # MCP 服务配置
        `-- tools/
            |-- tool_registry.py        # MCP 与 R1 工具定义
            |-- mcp_tools.py            # MCP Streamable HTTP 客户端
            |-- rag_tool.py             # 持久化 TravelRAG
            `-- r1_tool.py              # 独立异步 R1 封装
```

## 环境要求

- Python 3.11 或更高版本
- DashScope API Key
- DeepSeek API Key，复杂分析需要
- 至少一个可访问的 MCP 服务，实时查询需要

模型通过在线 API 调用，不需要本地 GPU。

## 安装

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ./aggentic_RAG
```

### macOS 或 Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ./aggentic_RAG
```

`setup.py` 会读取 `aggentic_RAG/requirements.txt`，不需要再安装第二份依赖清单。

## 模型配置

推荐创建 `aggentic_RAG/.env`：

```dotenv
DASHSCOPE_API_KEY=your-dashscope-api-key
DEEPSEEK_API_KEY=your-deepseek-api-key

LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=

MCP_CONFIG_PATH=travel_agent/config/servers_config.json
CHROMA_PERSIST_DIR=data/travel_vectordb
```

主 UI 也会在 `aggentic_RAG/.env` 不存在时尝试读取根目录 `.env`。包内配置默认读取 `aggentic_RAG/.env`。
部署时可将 `CHROMA_PERSIST_DIR` 设为持久卷的绝对路径。

不要提交真实 API Key。

## MCP 配置

编辑 `aggentic_RAG/travel_agent/config/servers_config.json`：

```json
{
  "mcp_servers": [
    {
      "name": "12306 Server",
      "url": "https://your-12306-mcp-endpoint"
    },
    {
      "name": "Gaode Server",
      "url": "https://your-gaode-mcp-endpoint"
    },
    {
      "name": "bazi Server",
      "url": "https://your-bazi-mcp-endpoint"
    },
    {
      "name": "flight Server",
      "url": "https://your-flight-mcp-endpoint"
    }
  ]
}
```

服务器名称必须与示例完全一致。空 URL 会被保留为未连接服务，调用时返回明确错误。

MCP 客户端实现了：

- JSON-RPC 初始化
- Session ID 管理
- Streamable HTTP 工具调用
- 网络超时和连接错误重试
- 运行时重新初始化
- 按需连接，不阻塞应用首屏
- 连接资源清理

## 启动

在项目根目录运行：

```bash
streamlit run app.py
```

默认地址：

```text
http://localhost:8501
```

## 持久化知识库

### 通过 UI 导入

侧边栏支持上传：

- `.txt`
- `.md`
- `.pdf`
- `.csv`

导入流程：

1. 上传文件临时落盘，用于文档解析。
2. 为文档写入稳定的原始文件名。
3. 按配置进行文本分块。
4. 使用 DashScope `text-embedding-v4` 生成向量。
5. 写入 `aggentic_RAG/data/travel_vectordb`。
6. 使用稳定内容 ID 跳过重复分块。

上传时使用的临时文件会自动删除，向量数据库会保留。应用重启后即使不重新上传文件，也会加载已有知识库并注册 `rag_search`。

侧边栏会显示知识库文档数和分块数。

### 通过代码导入

```python
from travel_agent.tools.rag_tool import TravelRAG

rag = TravelRAG()
result = rag.build_knowledge_base(
    "./aggentic_RAG/data/travel_docs",
    file_type="directory",
)
print(result)
```

查询统计：

```python
print(rag.get_stats())
```

按来源删除：

```python
deleted = rag.delete_by_source("sample_guides.txt")
print(deleted)
```

## 常见问题

### 缺少 DashScope API Key

知识库初始化和 Qwen 调用都需要 `DASHSCOPE_API_KEY`。确认它位于 `aggentic_RAG/.env`。

### PDF 导入失败

重新安装项目依赖：

```bash
pip install -e ./aggentic_RAG
```

依赖清单已包含 `pypdf`。

### MCP 工具不可用

检查：

1. URL 是否为空。
2. 服务名称是否完全一致。
3. 服务是否支持 MCP Streamable HTTP。
4. 服务器是否返回 `mcp-session-id`。
5. 部署环境是否能访问对应地址。

### 清空聊天后仍有旧消息

“清空聊天记录”会同时清除界面消息和 LangChain 会话历史。知识库不会被清除。

## 当前限制

- Streamlit、Agent 和工具包装仍集中在单个 `app.py`
- MCP、模型和 Embedding 都依赖外部服务
- 当前没有用户隔离，所有用户共享同一持久化知识库目录
- 没有自动化测试、限流、监控和任务队列
- 第三方工具失败时，最终方案可能只包含部分实时信息

公开部署前，应增加用户鉴权、知识库隔离、上传大小限制、日志和接口限流。

## 安全说明

- 不要提交 API Key、Cookie 或访问令牌
- 私有 MCP URL 建议通过部署平台 Secret 管理
- 上传文件应增加大小、类型和内容安全检查
- 票价、天气、酒店和航班信息应以官方平台为准

## License

本项目使用 [MIT License](LICENSE)。
