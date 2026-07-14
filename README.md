# 智能旅游规划助手

一个基于 Streamlit、LangChain ReAct、Qwen、DeepSeek R1、RAG 和 MCP 工具的旅游规划应用。用户可以通过自然语言描述出发地、目的地、日期、预算和偏好，系统会根据问题复杂度调用模型与外部工具，生成旅行建议。

> 当前主入口是项目根目录的 `app.py`。`aggentic_RAG/travel_agent` 中的 LangGraph 工作流和自定义执行器属于兼容/备用实现，不是 Streamlit UI 的实际执行链路。

## 当前功能

- 从自然语言中提取出发地、目的地、日期、天数、预算和偏好
- 识别简单查询、复杂约束和多目的地行程
- 使用 Qwen `qwen-plus` 完成需求提取和 ReAct 工具调用
- 在复杂或多目的地场景中使用 DeepSeek `deepseek-reasoner` 辅助路线、预算和风险分析
- 通过 MCP 服务查询火车票、高德地图、天气、酒店、黄历和航班
- 可选上传 TXT、PDF、CSV 文档，建立本次会话使用的临时 RAG 检索器
- 使用 Streamlit 展示对话、工具状态和基础配置

## 运行架构

```text
用户输入
   |
   v
Streamlit UI (app.py)
   |
   +-- Qwen 预分析
   |     +-- 提取目的地、日期、预算等信息
   |     +-- 判断 simple / complex / multi_destination
   |
   +-- LangChain ReAct Agent
         +-- 简单场景：Qwen 自主选择工具
         +-- 复杂场景：提示 Agent 先调用 DeepSeek R1
         |
         +-- 可用数据源
               +-- 上传文档 RAG
               +-- 12306 MCP
               +-- 高德地图 MCP
               +-- 黄历 MCP
               +-- 航班 MCP
```

主流程说明：

1. `pre_analyze_query` 调用 Qwen 提取结构化旅行信息。
2. 系统结合模型结果和多目的地规则判断场景类型。
3. 简单场景直接进入 LangChain ReAct Agent。
4. 复杂或多目的地场景会增强输入，要求 Agent 优先调用 `r1_analysis`。
5. Agent 根据提示词和工具描述查询实时数据，最终生成中文旅行方案。

## 工具列表

主 UI 会根据 `tool_registry.py` 注册以下工具：

| 工具 | 数据来源 | 用途 |
| --- | --- | --- |
| `rag_search` | 上传文档 | 查询攻略、景点、美食等文档内容；仅上传文档后可用 |
| `train_query` | 12306 MCP | 查询车站代码、车次和票务信息，并尝试补充自驾路线 |
| `gaode_poi_search` | 高德 MCP | 搜索景点、餐厅、购物等 POI |
| `gaode_hotel_search` | 高德 MCP | 搜索酒店或民宿 |
| `gaode_weather` | 高德 MCP | 查询城市天气 |
| `gaode_geo` | 高德 MCP | 将地址转换为经纬度 |
| `gaode_driving` | 高德 MCP | 查询驾车距离、时间和路线 |
| `lucky_day` | 八字黄历 MCP | 查询指定日期的农历和宜忌 |
| `flight_query` | 航班 MCP | 查询出发地、目的地和日期对应的航班 |
| `r1_analysis` | DeepSeek API | 分析复杂路线、预算分配、风险和备选方案 |

工具是否能返回数据取决于对应 API Key、MCP URL、服务状态和第三方接口能力。未配置 MCP 服务时，应用仍可能启动，但实时查询会返回不可用或连接错误。

## 项目结构

```text
travel-planning-agent/
|-- app.py                              # Streamlit 主入口和实际 Agent 实现
|-- check_mcp_health.py                 # MCP 连接检查脚本
|-- README.md
|-- aggentic_RAG/
|   |-- requirements.txt                # UI 和常用运行依赖
|   |-- setup.py                        # travel_agent 包及包内依赖
|   |-- data/
|   |   |-- travel_docs/                # 示例旅游文档
|   |   `-- travel_vectordb/            # 包内 TravelRAG 使用的持久化 Chroma 数据
|   `-- travel_agent/
|       |-- config/
|       |   |-- settings.py             # 模型、RAG 和配置路径
|       |   |-- prompts.py              # 包内 LangGraph Prompt
|       |   `-- servers_config.json     # MCP 服务地址
|       |-- tools/
|       |   |-- tool_registry.py        # 主 UI 使用的工具定义
|       |   |-- mcp_tools.py            # MCP 连接、调用与重试
|       |   |-- rag_tool.py              # 持久化 TravelRAG 实现
|       |   `-- r1_tool.py               # 异步 DeepSeek R1 封装
|       |-- graph/
|       |   |-- state.py                 # LangGraph 状态定义
|       |   |-- nodes.py                 # 兼容工作流节点
|       |   `-- workflow.py              # 兼容 LangGraph 工作流
|       |-- core/
|       |   `-- agent_executor.py        # 备用自定义执行器，主 UI 未使用
|       `-- app.py                       # 包内 LangGraph 示例入口
`-- .env                                 # 可选：主 UI 的备用环境变量位置
```

## 环境要求

- Python 3.11 或更高版本
- 可访问 DashScope 和 DeepSeek API
- 至少一个可用的 MCP 服务，才能使用对应实时查询功能
- Windows、macOS 或 Linux

需要的密钥：

- `DASHSCOPE_API_KEY`：必需，用于 Qwen 和文档向量化
- `DEEPSEEK_API_KEY`：复杂分析需要；不配置时 `r1_analysis` 不可用
- `LANGCHAIN_API_KEY`：可选，仅在启用 LangSmith 追踪时需要

## 安装

当前项目的 UI 依赖和包内依赖分别维护在 `requirements.txt` 与 `setup.py` 中。为覆盖主 UI、MCP 和兼容工作流，请同时执行以下安装步骤。

### 1. 创建虚拟环境

PowerShell：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

macOS 或 Linux：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

### 2. 安装项目依赖

在项目根目录执行：

```bash
pip install -r aggentic_RAG/requirements.txt
pip install -e ./aggentic_RAG
pip install pypdf
```

说明：

- `requirements.txt` 提供 Streamlit、LangChain Classic 和 `nest-asyncio` 等 UI 依赖。
- 可编辑安装提供 `travel_agent`、LangGraph 和 `openai-agents` 等包内依赖。
- `pypdf` 用于 PDF 上传；不需要 PDF 时可以不安装。

## 配置模型

推荐在 `aggentic_RAG/.env` 创建环境变量文件，因为主 UI 和包内兼容入口都能读取该位置：

```dotenv
DASHSCOPE_API_KEY=your-dashscope-api-key
DEEPSEEK_API_KEY=your-deepseek-api-key

LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=

MCP_CONFIG_PATH=travel_agent/config/servers_config.json
```

根目录 `.env` 仅作为 Streamlit 主入口的备用位置。包内 `travel_agent.config.settings` 默认读取 `aggentic_RAG/.env`。

不要提交包含真实密钥的 `.env` 文件。

## 配置 MCP 服务

编辑 `aggentic_RAG/travel_agent/config/servers_config.json`：

```json
{
  "mcp_servers": [
    {
      "name": "12306 Server",
      "url": "https://your-12306-server.example/sse"
    },
    {
      "name": "Gaode Server",
      "url": "https://your-gaode-server.example/sse"
    },
    {
      "name": "biying Server",
      "url": ""
    },
    {
      "name": "bazi Server",
      "url": "https://your-bazi-server.example/sse"
    },
    {
      "name": "flight Server",
      "url": "https://your-flight-server.example/sse"
    }
  ]
}
```

服务器名称必须与代码中的名称完全一致：

- `12306 Server`
- `Gaode Server`
- `bazi Server`
- `flight Server`
- `biying Server` 当前存在于配置模板中，但主 UI 没有注册对应的必应搜索工具

空 URL 会被跳过。仓库默认的 `servers_config.json` 不包含可用 URL，必须自行配置外部 MCP 服务。

## 启动应用

在项目根目录执行：

```bash
streamlit run app.py
```

默认访问地址：

```text
http://localhost:8501
```

主界面支持：

- 输入旅行需求并查看回答
- 上传 TXT、PDF 或 CSV 攻略文档
- 查看本次启动注册的工具列表
- 清空界面聊天记录

当前主入口实际使用的 Agent 最大迭代次数固定为 30。侧边栏虽然显示迭代次数滑块，但该滑块值目前不会改变实际执行上限。

## 使用示例

简单查询：

```text
杭州有哪些适合第一次去的景点？
```

完整规划：

```text
帮我规划 2026 年 10 月 3 日从上海去青岛的 4 天游，预算 5000 元，喜欢海边和当地美食。
```

复杂多目的地：

```text
一家三口从北京出发，先去西安再去成都，共 7 天，预算 12000 元，有老人同行，请比较高铁和飞机并安排住宿。
```

建议提供明确的年份、出发地、目的地、天数和预算。信息不完整时，模型可能基于上下文推断，实时票价和可售状态仍应以官方平台为准。

## 上传文档与 RAG

### Streamlit 主入口

侧边栏上传功能支持：

- TXT
- PDF，需要安装 `pypdf`
- CSV

上传后，应用会：

1. 将文件写入临时目录。
2. 以 500 字符分块、100 字符重叠切分文档。
3. 使用 DashScope `text-embedding-v3` 生成向量。
4. 创建临时 Chroma 检索器，并注册 `rag_search`。

该检索器没有配置持久化目录，主要服务于当前 Streamlit 运行和缓存周期，不会写入仓库中的 `aggentic_RAG/data/travel_vectordb`。

### 包内持久化 TravelRAG

`travel_agent.tools.rag_tool.TravelRAG` 是另一套持久化实现，支持 TXT、Markdown、PDF、CSV 和目录导入：

```python
from travel_agent.tools.rag_tool import TravelRAG

rag = TravelRAG()
rag.build_knowledge_base(
    "./aggentic_RAG/data/travel_docs",
    file_type="directory",
    force_recreate=False,
)
```

它默认把数据保存到 `aggentic_RAG/data/travel_vectordb`，但主 Streamlit UI 当前不会自动使用该实例。

## MCP 健康检查

安装完整依赖并配置 URL 后，在项目根目录运行：

```bash
python check_mcp_health.py
```

脚本会检查以下服务是否已注册且可以列出工具：

- 12306 Server
- Gaode Server
- bazi Server
- flight Server

注意：MCP 管理器当前会跳过空 URL，并忽略单个服务器初始化异常，因此健康检查比 Streamlit 侧边栏的工具数量更能反映真实连接状态。

## 兼容与备用入口

项目仍保留以下实现，主要用于兼容旧代码或继续开发：

- `travel_agent.graph.workflow.create_react_workflow`：LangGraph ReAct 工作流
- `travel_agent.graph.workflow.create_travel_workflow`：旧的线性 LangGraph 工作流
- `travel_agent.core.agent_executor.AgentExecutor`：不依赖 LangGraph 路由的备用执行器
- `travel_agent.app`：调用当前 LangGraph 工作流的示例入口

运行包内示例前，需要在 `aggentic_RAG/.env` 配置模型密钥，并完成 MCP 配置：

```bash
python -m travel_agent.app
```

这些入口与根目录 `app.py` 的状态管理、工具包装和执行策略不同，不应视为同一运行链路。

## 常见问题

### `ModuleNotFoundError: nest_asyncio`

```bash
pip install -r aggentic_RAG/requirements.txt
```

### 无法导入 `agents.mcp`

```bash
pip install -e ./aggentic_RAG
```

该模块由 `openai-agents` 提供，不是 `mcp` 包本身提供的。

### PDF 上传失败

```bash
pip install pypdf
```

### 模型提示缺少 API Key

确认 `aggentic_RAG/.env` 包含有效的 `DASHSCOPE_API_KEY`。复杂分析还需要 `DEEPSEEK_API_KEY`。

### 工具已显示但实时查询失败

检查：

1. `servers_config.json` 中的 URL 是否为空。
2. MCP 服务名称是否与代码完全一致。
3. SSE 地址是否可访问。
4. MCP 服务是否提供代码中使用的工具名称。
5. 运行 `python check_mcp_health.py` 查看实际连接结果。

### 清空聊天后模型仍引用旧内容

主 UI 的展示消息与 LangChain `StreamlitChatMessageHistory` 当前使用不同的会话状态键。清空按钮只清除界面消息；如需彻底清空上下文，可刷新或重新启动 Streamlit 会话。

## 当前限制

- 依赖外部模型和 MCP 服务，仓库本身不提供这些在线服务
- 默认 MCP 配置为空，克隆后不能直接查询实时数据
- 主 UI 的文档 RAG 不使用仓库内持久化向量库
- 预分析依赖模型输出合法 JSON；解析失败时会回退到简单场景
- 第三方工具失败时 Agent 会使用已有信息继续生成答案，结果可能不完整
- 主 UI、LangGraph 和备用执行器尚未统一为同一套执行架构
- 项目当前没有自动化测试

## 安全说明

- 不要把 API Key、Cookie 或访问令牌写入源码或提交到 Git
- MCP URL 如果包含鉴权参数，不应直接提交到已跟踪的配置文件
- 票价、天气、航班和酒店信息来自第三方服务，预订前请到官方渠道复核
- 黄历信息仅作为文化参考，不应替代安全、医疗或专业建议

## License

本项目使用 [MIT License](LICENSE)。
