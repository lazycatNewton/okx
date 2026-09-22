# okx-backend

OKX 行情连接服务后端（REQ-001 核心闭环阶段）。实现依据见仓库根目录的
[okx-requirements.md](../okx-requirements.md)；工作规则见 [AGENTS.md](../AGENTS.md) / [CLAUDE.md](../CLAUDE.md)。

## 当前已实现范围

核心端到端闭环：

- 用户名密码登录、不透明会话 Cookie（Redis 存储）、连续 5 次失败冻结 15 分钟、新浏览器登录挤出旧会话。
- 产品发现（`GET /api/v5/public/instruments` SPOT/SWAP）与永久版本化目录。
- 产品选择（`PUT /api/subscriptions/products`），仅接受 `state=live`。
- 持续采集 M01（ticker）、M02（成交价 K 线 1s/5m/15m/1D）、M05（books5 五档）：
  - OKX WebSocket 客户端自实现（心跳、指数退避重连、连接代次、desired/active 订阅集合）。
  - MySQL 落库（去重 upsert）+ Redis 最新状态缓存。
- 浏览器 `/ws/app` 实时分发：`activate-product`/`deactivate-product`，`snapshot`→`update`→`empty` 信封。
- `GET /api/market/{instId}/candles` 查询已保存的 K 线序列。
- `GET /api/bootstrap` 恢复登录后状态。

尚未实现（下一步）：M10-M16、M22、M23、M25，以及内部策略消费者接口 `/internal/v1/*`。

## 技术栈

Python 3.13 + uv + FastAPI + SQLAlchemy(asyncio) + Alembic + MySQL 8.0+（远程）+ Redis。
OKX REST 调用直接用 httpx；WS 自实现（未使用 `python-okx` 的 WS 封装，原因见
`okx-requirements.md`「已确定的系统组成」一节）。

## 本地开发

```bash
# 安装依赖
uv sync

# 配置 .env.localhost（本地开发用；ENV=prod 时完全不读取该文件，见下方「启动环境 ENV」）
cp .env.localhost.example .env.localhost  # 按需修改其中的连接信息

# 迁移（默认按 localhost；生产环境需显式传 ENV=prod）
uv run alembic upgrade head

# 启动
uv run uvicorn okx_backend.main:app --reload
```

### 启动环境 `ENV`（未设置时默认为 `localhost`）

环境变量 `ENV` 决定两件事：配置从哪里装载、Nacos 是否启用。未设置时默认按 `localhost` 处理（方便本地开发直接运行、无需每次都写 `ENV=localhost`）；取值非法（既不是 `localhost` 也不是 `prod`）会直接抛异常终止启动，不做静默降级。**生产部署必须显式设置 `ENV=prod`**，否则会按本地开发模式启动（跳过 Nacos、尝试读取 `.env.localhost`）。

| `ENV` 取值 | 配置装载方式 | Nacos |
| --- | --- | --- |
| `localhost`（或未设置） | 从 `.env.localhost` 文件 + OS 环境变量读取（OS 环境变量优先级更高，可覆盖文件中的值） | 强制禁用，完全跳过，不需要真实 Nacos 服务；MySQL/Redis 直接用 `.env.localhost` 中的值 |
| `prod` | **不加载任何 dotenv 文件**，全部配置（含 OKX API 凭证、会话参数、`retention_days` 等所有字段）必须来自真实 OS 环境变量 | 强制启用；MySQL/Redis 账号密码必须来自 Nacos 远程配置（见下节），不再依赖 `NACOS_ENABLED` 开关（该变量已废弃、不再读取） |

`ENV=prod` 下如果只设置了部分 OS 环境变量、遗漏了某个必填项，字段会退回代码中的默认值（如 `mysql_host` 默认 `127.0.0.1`）而不是报错——这是 pydantic-settings 字段默认值的行为，不是本项目对"生产环境"的静默降级；生产部署清单应显式列出所有需要设置的 `OKX_APP_*` 环境变量，不依赖默认值兜底。

### 环境变量（`OKX_APP_` 前缀）

| 变量 | 说明 |
| --- | --- |
| `OKX_APP_MYSQL_HOST` / `_PORT` / `_USER` / `_PASSWORD` / `_DATABASE` | 远程 MySQL 8.0+ 连接信息；`ENV=prod` 时被 Nacos 远程配置覆盖 |
| `OKX_APP_REDIS_HOST` / `_PORT` / `_DB` / `_PASSWORD` | Redis 连接信息；`ENV=prod` 时 host/port/password 被 Nacos 远程配置覆盖 |
| `OKX_APP_OKX_API_KEY` / `_SECRET` / `_PASSPHRASE` | M23 经济日历鉴权（可选；未配置时应用返回空数据集） |
| `OKX_APP_DEBUG` | `true` 时开启 SQL echo，仅本地调试用 |

### Nacos 远程配置（`ENV=prod` 时必需，`ENV=localhost` 时完全不使用）

参照 [`stock-view`](/Users/lazycatnewton/development-repo/stock-view) 后端的既有模式：Nacos 客户端自身的连接信息（服务地址、命名空间、账号密码）来自服务器环境变量，业务凭证（MySQL/Redis 账号密码）保存在 Nacos 的远程配置项中，启动时拉取一次并覆盖 `Settings`。

| 变量（无 `OKX_APP_` 前缀） | 说明 |
| --- | --- |
| `NACOS_SERVER_ADDR` | Nacos 服务地址，`host:port` 形式 |
| `NACOS_NAMESPACE_ID` | 命名空间 ID，默认空 |
| `NACOS_USERNAME` / `NACOS_PASSWORD` | 登录 Nacos 的账号密码 |
| `NACOS_DATA_ID` / `NACOS_GROUP` | 远程配置的 Data ID 与分组 |
| `NACOS_TIMEOUT_MS` | 拉取超时（毫秒） |

Nacos 侧远程配置内容（YAML）预期结构：

```yaml
database:
  host: mysql-host
  port: 3306
  user: okx_app
  password: "***"
  name: okx_app
redis:
  host: redis-host
  port: 6379
  username: default   # 可选
  password: "***"      # 可选
```

启动流程：应用/迁移进程启动时，若 `ENV=prod`，先同步拉取一次该配置并覆盖
`OKX_APP_MYSQL_*`/`OKX_APP_REDIS_*`，再进行任何数据库/缓存连接；拉取失败直接中止启动，
不会静默回退到本地默认值。**Nacos 侧的 Data ID、Group 及 YAML 结构目前是按 stock-view
既有约定实现的假设，尚未与用户核对当前 Nacos 实例上实际发布的内容，接入真实 Nacos 前需要
确认这些细节。**

## 测试与检查

```bash
uv run ruff check .
uv run mypy src
uv run pytest -v
```

当前 11 项单元测试覆盖：密码哈希/用户名校验、WS 频道去重、Realtime Hub（含
"BrowserConnection 不可哈希"回归测试）、K 线 upsert 列名映射回归测试。

已在真实环境中验证（非 mock）：连接真实 OKX 全球站公共 REST/WS、写入本地 MySQL/Redis、
浏览器 WebSocket 端到端 snapshot→update 流程、服务重启后自动恢复采集。
