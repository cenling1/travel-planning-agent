# 智能旅行规划助手

一个前后端分离的 AI 旅行规划应用。Vue 3 提供旅行工作台、知识库和账号管理界面，FastAPI 负责会话、文档、混合 RAG 和旅行 Agent，PostgreSQL + pgvector 用于生产环境的关系数据与向量检索。

## 核心能力

- DeepSeek Chat 预分析需求，并通过通用工具目录自主规划工具调用
- 使用 JSON ReAct 风格的“规划 → 执行 → Observation → 补充规划”链路
- 识别简单、复杂和多目的地旅行场景
- DeepSeek R1 辅助复杂路线和约束分析
- MCP Streamable HTTP 对接 12306 实时车次服务
- TXT、Markdown、PDF、CSV 文档导入、删除和重新索引
- pgvector 语义检索与 BM25 关键词检索融合
- 基于语义、关键词、覆盖率和分块质量的二次排序
- 回答返回文件名、页码、分块和引用编号
- 会话和消息持久化，可恢复历史对话
- 多用户隔离：会话、文档、检索和长期记忆均按用户归属过滤
- 长期偏好记忆：自动保存明确偏好，并提供查看和删除入口
- SQLite 离线开发模式和 PostgreSQL/pgvector 生产模式
- RAG 评测集及 Recall@K、MRR、关键词覆盖率指标

## 架构

```text
Vue 3 + Nginx
      |
      | /api + NDJSON stream
      v
FastAPI backend/main.py
      |
      +-- TravelAgentService
      |     +-- 需求预分析与场景路由
      |     +-- 通用 Agent 工具规划循环
      |     |     +-- Hybrid RAG + citations
      |     |     +-- 12306 实时车次 MCP
      |     |     `-- 工具失败观察与补充调用
      |     `-- DeepSeek Chat / Reasoner 综合生成
     |
      +-- Conversation API
      +-- Memory API
      `-- Document API
             |
             +-- PostgreSQL + pgvector（生产）
             `-- SQLite + 本地向量计算（开发）
```

## 项目结构

```text
travel-planning-agent/
|-- frontend-web/                  # Vue 3 + TypeScript 前端
|-- backend/
|   |-- main.py                    # FastAPI 入口
|   |-- api/                       # 聊天、会话、文档、健康检查
|   |-- integrations/              # DeepSeek Reasoner 与 MCP 客户端
|   |-- repositories/              # SQLAlchemy 数据访问
|   |-- services/                  # Agent、通用工具目录、RAG、Embedding、MCP
|   |-- models.py                  # 会话、消息、文档、向量分块、长期记忆
|   `-- schemas.py                 # Pydantic API 模型
|-- migrations/                    # Alembic 数据库迁移
|-- config/                        # MCP 配置模板，本地配置不提交
|-- evaluation/rag_questions.json  # RAG 评测集
|-- scripts/
|   |-- evaluate_rag.py            # 检索评测
|   `-- migrate_chroma_to_database.py
|-- tests/                         # 单元与服务测试
|-- Dockerfile
|-- docker-compose.yml
`-- requirements.txt               # Python 后端依赖
```

## 安装

要求 Python 3.11 或更高版本。

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Python 后端依赖统一维护在根目录 `requirements.txt`。

## 配置

复制根目录 `.env.example` 为 `.env` 并配置：

```dotenv
DASHSCOPE_API_KEY=your-dashscope-api-key
DEEPSEEK_API_KEY=your-deepseek-api-key
DEEPSEEK_CHAT_MODEL=deepseek-v4-pro
DEEPSEEK_REASONING_MODEL=deepseek-v4-pro
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_TEMPERATURE=0.7
DEEPSEEK_THINKING_ENABLED=false

# 本地不配置时自动使用 SQLite
DATABASE_URL=postgresql+psycopg://travel_agent:travel_agent@localhost:5432/travel_agent
UPLOAD_DIR=data/uploads
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIMENSION=1024

MCP_CONFIG_PATH=config/servers_config.json
BACKEND_URL=http://localhost:8000
TRAVEL_CLIENT_ID=local

# 本地默认关闭认证；生产环境见 .env.production.example
AUTH_ENABLED=false
AUTH_REGISTRATION_ENABLED=true
JWT_SECRET=
JWT_ACCESS_MINUTES=15
JWT_REFRESH_DAYS=30
RATE_LIMIT_PER_MINUTE=0
MAX_INFLIGHT_REQUESTS=0
```

DeepSeek Key 用于需求提取、复杂路线分析和最终回答，Agent 的全部模型推理均由 DeepSeek 完成。DashScope 仅用于知识库文本 Embedding；没有 DashScope Key 时会使用确定性的本地 Hash 向量。没有 DeepSeek Key 时，回答会进入明确的离线降级模式。

## 本地启动

终端一：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000
```

终端二：

```powershell
cd frontend-web
npm ci
npm run dev
```

后端不在默认的 8000 端口时，可在启动前设置 `VITE_API_PROXY_TARGET`（例如 `http://localhost:8001`）。

访问地址：

- Vue 前端：http://localhost:5173
- API：http://localhost:8000
- Swagger：http://localhost:8000/docs

使用开发 Compose 时，Vue + Nginx 入口为 http://localhost:8080。

未设置 `DATABASE_URL` 时，后端使用 `data/travel_agent.db`。

## Docker Compose

```bash
docker compose up --build
```

Compose 会启动：

- `postgres`：PostgreSQL 16 + pgvector
- `backend`：FastAPI 和 Alembic迁移
- `web`：Vue 3 构建产物和 Nginx

PostgreSQL数据和上传文档分别保存在持久卷中。

生产部署请使用独立配置：

```bash
docker compose --env-file .env -f docker-compose.prod.yml up -d --build
```

生产配置由 `web` 服务使用 Nginx 提供 Vue 静态资源、HTTPS 和 API 反向代理，仅公开 80/443；应用使用数据库账号、Argon2 密码哈希、HttpOnly Cookie 刷新令牌和 `user/admin` 角色权限。后端和 PostgreSQL 保持在 Docker 内网。详细步骤见 `docs/deployment.md`。

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
| `GET/POST` | `/api/memories` | 查询或写入长期记忆 |
| `DELETE` | `/api/memories/{id}` | 删除长期记忆 |
| `POST` | `/api/auth/register` | 注册账号（可关闭） |
| `POST` | `/api/auth/login` | 登录并签发访问/刷新令牌 |
| `POST` | `/api/auth/refresh` | 轮换刷新令牌 |
| `POST` | `/api/auth/logout` | 退出当前会话 |
| `GET` | `/api/auth/me` | 当前账号 |
| `GET/POST` | `/api/admin/users` | 管理员查询或创建账号 |
| `PATCH` | `/api/admin/users/{id}` | 管理员调整角色或状态 |

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
pip install -r requirements-migration.txt
.\.venv\Scripts\python.exe scripts/migrate_chroma_to_database.py
```

脚本默认读取 `data/legacy_chroma` 的 `travel_knowledge` 集合，按来源合并内容并写入新知识库。

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
$env:AUTH_ENABLED="false"
$env:PYTHONIOENCODING="utf-8"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
cd frontend-web
npm test
```

测试覆盖流式 NDJSON、Multipart 上传、并发令牌刷新、Cookie 轮换、文档生命周期、混合检索、离线 Agent、JWT 身份隔离、角色权限、MCP 重试和旧 Chroma 稳定 ID。

## 工程设计与扩展性

- 会话数据通过 `client_id` 隔离，认证层可进一步接入 JWT 或第三方身份服务
- 检索层采用 pgvector 语义检索、BM25 关键词检索与轻量二次排序，组件之间保持解耦，便于替换中文检索引擎或 Cross-Encoder Reranker
- 文档解析、分块、Embedding 与索引流程采用独立服务封装，可扩展为异步任务队列以处理大规模文档
- MCP 工具层统一管理外部服务连接、超时、重试与异常返回，便于继续增加酒店、天气和交通数据源
- 数据访问层同时适配 SQLite 与 PostgreSQL/pgvector，兼顾本地开发效率和生产环境扩展能力
- 尚未接入邮件服务；忘记密码需要管理员在账号管理界面重置
- BM25采用应用层分词，大规模语料应接入更专业的中文检索引擎
- 当前二次排序为轻量规则模型，不是Cross-Encoder Reranker
- 文档索引在请求内完成，大文件应改为异步任务队列
- 外部实时数据取决于MCP服务可用性
- Docker配置已提供，但需要本机安装Docker后才能运行

## 安全

- 不要提交 `.env`、API Key、Cookie或访问令牌
- 上传文件限制为20MB，并由后端再次校验文件类型
- MCP服务地址如果包含私有鉴权信息，应改为环境变量或Secret管理
- 生产环境不要暴露 PostgreSQL 5432 或 FastAPI 8000 端口
- 车次和票务信息应以 12306 官方渠道为准

## License

本项目使用 [MIT License](LICENSE)。
