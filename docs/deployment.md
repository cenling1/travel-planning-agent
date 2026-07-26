# 生产部署说明

生产入口使用 Nginx 提供 Vue 静态资源、HTTPS 和 API 反向代理，公网只开放 80/443。PostgreSQL 和 FastAPI 仅位于 Docker 内网。应用账号由 PostgreSQL 保存，密码使用 Argon2 哈希；访问令牌为短期 JWT，刷新令牌会轮换，数据库中只保存其 SHA-256 摘要。

## 服务器准备

推荐 Ubuntu 22.04/24.04、4 核 CPU、8 GB 内存、40 GB 以上 SSD，并安装 Docker Engine 与 Docker Compose Plugin。将域名解析到服务器，并在防火墙中只开放：

- 80/tcp
- 443/tcp
- 受限来源的 SSH

不要向公网映射 PostgreSQL `5432` 或 FastAPI `8000`。

## 生产配置

复制配置模板：

```bash
cp .env.production.example .env
chmod 600 .env
```

至少完成以下配置：

1. 设置 `DOMAIN` 和与域名一致的 `CORS_ORIGINS`。使用 Certbot 或云平台签发证书，将完整证书链和私钥的宿主机路径分别写入 `TLS_CERT_HOST_PATH`、`TLS_KEY_HOST_PATH`；续期后执行 `docker compose --env-file .env -f docker-compose.prod.yml exec web nginx -s reload`。
2. 为 PostgreSQL 设置独立的长随机密码。该密码会出现在数据库连接 URL 中，建议使用 URL 安全字符，例如 `A!` 加 48 位十六进制随机值：

```bash
printf 'A!%s\n' "$(openssl rand -hex 24)"
```
3. 生成 JWT 密钥并写入 `JWT_SECRET`：

```bash
openssl rand -hex 32
```

4. 设置首次管理员的 `BOOTSTRAP_ADMIN_USERNAME` 和 `BOOTSTRAP_ADMIN_PASSWORD`。密码至少 10 位，并包含大写字母、小写字母、数字、特殊字符中的三类。
5. 决定是否开放自助注册。生产模板默认设置 `AUTH_REGISTRATION_ENABLED=false`，由管理员在界面中创建账号；确需公开注册时再显式开启。
6. 填写 DeepSeek、DashScope 等模型配置。`AGENT_MAX_ROUNDS` 控制工具规划轮数，`AGENT_MAX_TOOL_CALLS` 限制单次请求最多执行的工具数量。
7. 将私有 MCP 配置放到 `MCP_CONFIG_HOST_PATH` 指向的位置，并限制为部署用户只读。

不要提交 `.env`、MCP 配置、数据库、上传文件、访问令牌或备份文件。`JWT_SECRET` 变更后，所有现有登录会话会立即失效。

## 首次启动

```bash
docker compose --env-file .env -f docker-compose.prod.yml up -d --build
docker compose --env-file .env -f docker-compose.prod.yml ps
docker compose --env-file .env -f docker-compose.prod.yml logs -f backend
```

后端启动前会自动执行 `alembic upgrade head`，然后创建配置中的首次管理员。确认管理员可以登录后，将 `.env` 中两个 `BOOTSTRAP_ADMIN_*` 值清空，并重新创建后端容器，避免初始密码长期留在容器环境中：

```bash
docker compose --env-file .env -f docker-compose.prod.yml up -d --force-recreate backend
```

## 账号与权限

角色只有两级：

- `user`：使用聊天、会话、文档、检索和长期记忆，且只能访问自己的数据。
- `admin`：拥有普通用户能力，并可创建账号、调整角色、停用账号和强制重置密码。

系统会阻止管理员降低或停用自己的当前账号，也会阻止停用最后一个可用管理员。改密、角色调整、账号停用和“退出全部设备”都会撤销该账号的全部刷新会话，并使已有访问令牌失效。

访问令牌默认有效 15 分钟，刷新令牌默认有效 30 天，可分别通过 `JWT_ACCESS_MINUTES`、`JWT_REFRESH_DAYS` 调整。刷新令牌每次使用后立即轮换；重放旧刷新令牌会撤销该账号的全部会话。

## 升级

拉取经过审核的版本后执行：

```bash
docker compose --env-file .env -f docker-compose.prod.yml up -d --build
docker compose --env-file .env -f docker-compose.prod.yml ps
```

升级前先做数据库和上传文件备份。数据库迁移由后端容器自动执行，不要手工修改生产表结构。

## 备份

```bash
set -a
. ./.env
set +a
bash scripts/backup.sh
```

备份包含 PostgreSQL 数据以及上传文件。账号、角色和刷新会话位于 PostgreSQL 中。上线后至少完成一次恢复到空环境的演练。

## 验收

部署后至少检查：

- `https://你的域名/` 显示应用登录界面，错误密码不能登录。
- 管理员可以创建普通账号、重置密码、调整角色和停用账号。
- 普通账号访问 `/api/admin/users` 返回 403，未登录访问业务 API 返回 401。
- A 用户上传的文档、会话和记忆，B 用户不可见，即使 B 伪造 `client_id` 也不可见。
- 修改密码或停用账号后，原访问令牌和刷新令牌均不可继续使用。
- `/health` 正常，且不泄露私有 MCP 地址或密钥。
- “你好”快速返回，不触发知识库或 MCP；12306 失败时不伪造车次结果。
- 重启容器后，账号、会话、文档和记忆不丢失。
- 公网无法访问 `5432`、`8000`，重复请求可触发 429 限流。
