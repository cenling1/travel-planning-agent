# 智能旅行规划助手

一个前后端分离的 AI 旅行规划应用。Streamlit 提供聊天和知识库管理界面，FastAPI 负责会话、文档、混合 RAG 和旅行 Agent，PostgreSQL + pgvector 用于生产环境的关系数据与向量检索。

## 核心能力

- Qwen 提取出发地、目的地、日期、预算和偏好
- 识别简单、复杂和多目的地旅行场景
- DeepSeek R1 辅助复杂路线和约束分析
- MCP Streamable HTTP 对接 12306、高德、黄历和航班服务
- TXT、Markdown、PDF、CSV 文档导入、删除和重新索引
- pgvector 语义检索与 BM25 关键词检索融合
- 基于语义、关键词、覆盖率和分块质量的二次排序
- 回答返回文件名、页码、分块和引用编号
- 会话和消息持久化，可恢复历史对话
- SQLite 离线开发模式和 PostgreSQL/pgvector 生产模式
- RAG 评测集及 Recall@K、MRR、关键词覆盖率指标

## 架构

```text
Streamlit app.py
      |
      | HTTP
      v
FastAPI backend/main.py
      |
      +-- TravelAgentService
      |     +-- Qwen / DeepSeek
      |     +-- MCP tools
      |     `-- Hybrid RAG + citations
      |
      +-- Conversation API
      `-- Document API
             |
             +-- PostgreSQL + pgvector（生产）
             `-- SQLite + 本地向量计算（开发）
```

## 项目结构

```text
travel-planning-agent/
|-- app.py                         # Streamlit API 前端
|-- frontend/api_client.py         # FastAPI 客户端
|-- backend/
|   |-- main.py                    # FastAPI 入口
|   |-- api/                       # 聊天、会话、文档、健康检查
|   |-- repositories/              # SQLAlchemy 数据访问
|   |-- services/                  # Agent、RAG、Embedding、MCP
|   |-- models.py                  # 会话、消息、文档、向量分块
|   `-- schemas.py                 # Pydantic API 模型
|-- migrations/                    # Alembic 数据库迁移
|-- evaluation/rag_questions.json  # RAG 评测集
|-- scripts/
|   |-- evaluate_rag.py            # 检索评测
|   `-- migrate_chroma_to_database.py
|-- tests/                         # 单元与服务测试
|-- Dockerfile
|-- docker-compose.yml
`-- aggentic_RAG/                  # 模型、MCP 和旧 Chroma 兼容模块
```

## 安装

要求 Python 3.11 或更高版本。

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ./aggentic_RAG
```

`setup.py` 会读取 `aggentic_RAG/requirements.txt`，只需要维护一份依赖清单。

## 配置

在项目根目录或 `aggentic_RAG/.env` 配置：

```dotenv
DASHSCOPE_API_KEY=your-dashscope-api-key
DEEPSEEK_API_KEY=your-deepseek-api-key

# 本地不配置时自动使用 SQLite
DATABASE_URL=postgresql+psycopg://travel_agent:travel_agent@localhost:5432/travel_agent
UPLOAD_DIR=aggentic_RAG/data/uploads
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIMENSION=1024

MCP_CONFIG_PATH=travel_agent/config/servers_config.json
BACKEND_URL=http://localhost:8000
```

没有 DashScope Key 时，Embedding 使用确定性的本地 Hash 向量，便于离线开发和测试；模型回答会进入明确的离线降级模式。

## 本地启动

终端一：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000
```

终端二：

```powershell
.\.venv\Scripts\streamlit.exe run app.py --server.port 8501
```

访问地址：

- 前端：http://localhost:8501
- API：http://localhost:8000
- Swagger：http://localhost:8000/docs

未设置 `DATABASE_URL` 时，后端使用 `aggentic_RAG/data/travel_agent.db`。

## Docker Compose

```bash
docker compose up --build
```

Compose 会启动：

- `postgres`：PostgreSQL 16 + pgvector
- `backend`：FastAPI 和 Alembic迁移
- `frontend`：Streamlit

PostgreSQL数据和上传文档分别保存在持久卷中。

## API

| 方法 | 地址 | 用途 |
| --- | --- | --- |
| `GET` | `/health` | 数据库和Embedding状态 |
| `GET` | `/health/tools` | MCP配置与连接状态 |
| `POST` | `/api/chat` | 生成旅行方案 |
| `GET/POST` | `/api/conversations` | 查询或创建会话 |
| `GET/DELETE` | `/api/conversations/{id}` | 恢复或删除会话 |
| `GET/POST` | `/api/documents` | 查询或上传文档 |
| `POST` | `/api/documents/search` | 混合检索 |
| `POST` | `/api/documents/{id}/reindex` | 重新索引 |
| `DELETE` | `/api/documents/{id}` | 删除文档和分块 |

## 混合 RAG

文档导入流程：

1. 校验扩展名、文件大小和文件名。
2. 保存原始文件并记录内容Hash。
3. 解析文档，保留来源和PDF页码。
4. 使用递归分块器切分内容。
5. 生成Embedding并写入数据库。
6. 检索时融合向量相似度与BM25分数。
7. 根据查询覆盖率、标题和分块质量二次排序。
8. 返回引用编号、文件名、页码和内容摘要。

PostgreSQL使用 `<=>` 余弦距离在数据库内筛选向量候选；SQLite模式在Python中计算余弦相似度。

## 迁移旧 Chroma 数据

```powershell
.\.venv\Scripts\python.exe scripts/migrate_chroma_to_database.py
```

脚本读取 `aggentic_RAG/data/travel_vectordb` 的 `travel_knowledge` 集合，按来源合并内容并写入新知识库。

## RAG 评测

先导入评测语料：

```powershell
curl.exe -F "files=@evaluation/corpus/chengdu.md" -F "files=@evaluation/corpus/beijing.md" -F "files=@evaluation/corpus/shanghai.md" http://localhost:8000/api/documents
```

运行评测：

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_rag.py --top-k 5
```

输出指标：

- `source_recall@K`：预期来源是否进入Top-K
- `mrr`：预期来源首次出现位置
- `expected_term_coverage`：预期事实是否出现在召回内容中

## 测试

```powershell
$env:PYTHONPATH="aggentic_RAG"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试覆盖文档生命周期、混合检索、离线Agent、会话隔离、MCP重试和旧Chroma稳定ID。

## 工程设计与扩展性

- 会话数据通过 `client_id` 隔离，认证层可进一步接入 JWT 或第三方身份服务
- 检索层采用 pgvector 语义检索、BM25 关键词检索与轻量二次排序，组件之间保持解耦，便于替换中文检索引擎或 Cross-Encoder Reranker
- 文档解析、分块、Embedding 与索引流程采用独立服务封装，可扩展为异步任务队列以处理大规模文档
- MCP 工具层统一管理外部服务连接、超时、重试与异常返回，便于继续增加酒店、天气和交通数据源
- 数据访问层同时适配 SQLite 与 PostgreSQL/pgvector，兼顾本地开发效率和生产环境扩展能力

## 安全

- 不要提交 `.env`、API Key、Cookie或访问令牌
- 上传文件限制为20MB，并由后端再次校验文件类型
- MCP服务地址如果包含私有鉴权信息，应改为环境变量或Secret管理
- 票价、酒店、天气和航班信息应以官方渠道为准

## License

本项目使用 [MIT License](LICENSE)。
