# 秋池（QiuChi）

[English](README.en.md) | 中文

---

## 项目简介

**秋池（QiuChi）** 是一个**生产级 MCP（Model Context Protocol）服务器框架**，基于 [FastMCP](https://github.com/modelcontextprotocol/python-sdk) 构建。通过分层清晰架构、插件化设计、中间件管道和统一配置管理，为企业提供开箱即用的 MCP 服务器开发体验。

**核心价值**：

- **协议合规** —— 完整实现 MCP 协议 Tools、Resources、Prompts 三大原语
- **架构清晰** —— Constants / Core / Plugins / Server / Runtime / Transport / Utils / Examples 八层职责分明
- **开箱即用** —— 装饰器一键注册、插件自动发现、中间件即插即用
- **生产就绪** —— 结构化日志、健康检查、容器化部署、TLS 支持

**适用场景**：

- 为 LLM 应用（Claude、GPT 等）快速搭建 MCP 工具服务
- 构建企业级 AI Agent 工具链平台
- 需要多传输层（Stdio / SSE / HTTP）灵活切换的 MCP 服务
- 需要插件化扩展和中间件治理的 AI 基础设施

---

## 快速开始

### 1. 环境要求

| 依赖项 | 最低版本 | 说明 |
|--------|---------|------|
| Python | >= 3.11 | 类型提示、异常组等特性要求 |
| uv | >= 0.1 | 推荐包管理器（[安装指南](https://docs.astral.sh/uv/getting-started/installation/)） |
| Git | >= 2.0 | 项目克隆 |

**Windows 环境**：

```powershell
# 安装 uv（PowerShell）
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 或使用 pip 安装
pip install uv
```

**Linux 环境**：

```bash
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 pip
pip install uv
```

**macOS 环境**：

```bash
# 使用 Homebrew 安装
brew install uv

# 或使用官方安装脚本
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 pip
pip install uv
```

### 2. 项目代码克隆

```bash
git clone https://github.com/chain-engine/x-QiuChi.git
cd x-QiuChi
```

### 3. 依赖同步安装

```bash
# 使用 uv 同步依赖（推荐）
uv sync

# 开发模式（包含测试、格式化、类型检查等工具）
uv sync --extra dev
```

### 4. 环境配置

```bash
# 复制配置文件
cp config.yaml.example config.yaml
```

**核心配置项说明**（`config.yaml`）：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `mcp.server_name` | `QiuChi` | MCP 服务器名称 |
| `mcp.version` | `0.1.0` | 服务器版本号（唯一事实源为 `pyproject.toml`，不建议在 YAML 中覆盖） |
| `mcp.transport` | `streamable-http` | 传输层类型：`stdio` / `sse` / `streamable-http` |
| `mcp.host` | `0.0.0.0` | HTTP 监听地址 |
| `mcp.port` | `8888` | HTTP 监听端口 |
| `mcp.json_response` | `true` | 是否启用 JSON 响应模式 |
| `logging.level` | `INFO` | 日志级别：`DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` |
| `logging.output` | `both` | 日志输出目标：`stderr` / `file` / `both` |
| `logging.file_path` | `logs/x-QiuChi_{time:YYYY-MM-DD-HH}.log` | 日志文件路径（支持时间模板） |
| `logging.rotation` | `1 hour` | 日志轮转周期 |
| `logging.retention` | `7 days` | 日志保留时长 |
| `features.tools` | `true` | 是否启用工具原语 |
| `features.resources` | `true` | 是否启用资源原语 |
| `features.prompts` | `true` | 是否启用提示词原语 |
| `features.middleware` | `true` | 是否启用中间件管道 |
| `plugins.auto_discovery` | `true` | 是否自动发现插件 |
| `plugins.discovery_paths` | `["src.extensions"]` | 插件扫描路径 |
| `middleware.auth.enabled` | `false` | 是否启用传输层 Bearer Token 认证 |
| `middleware.auth.tokens` | `[]` | 有效 Bearer Token 列表（enabled 时必填） |
| `opentelemetry.enabled` | `true` | 是否启用 OpenTelemetry |
| `opentelemetry.service_name` | `x-QiuChi` | 服务名（trace/metric 资源属性） |
| `opentelemetry.exporter` | `console` | 导出方式：`console` / `otlp` |
| `opentelemetry.otlp_endpoint` | `""` | OTLP 端点（exporter=otlp 时必填） |

**环境变量覆盖**：所有配置均可通过环境变量覆盖，优先级为 **环境变量 > YAML > 默认值**。常用环境变量：

| 环境变量 | 说明 |
|----------|------|
| `MCP_SERVER_NAME` | 服务器名称 |
| `MCP_TRANSPORT` | 传输层类型 |
| `MCP_HOST` | 监听地址 |
| `MCP_PORT` | 监听端口 |
| `LOGGING_LEVEL` | 日志级别 |
| `LOGGING_OUTPUT` | 日志输出目标 |
| `AUTH_ENABLED` | 是否启用传输层认证 |
| `AUTH_TOKENS` | 有效 token 列表（逗号分隔） |
| `TELEMETRY_ENABLED` | 是否启用 OpenTelemetry |
| `TELEMETRY_SERVICE_NAME` | 服务名 |
| `TELEMETRY_EXPORTER` | 导出方式（console / otlp） |
| `TELEMETRY_OTLP_ENDPOINT` | OTLP 端点 |

### 5. 启动服务

#### 方式一：CLI 启动（推荐）

```bash
# HTTP 模式（默认，端口 8888）
uv run x-QiuChi

# Stdio 模式（兼容 Claude Desktop）
uv run x-QiuChi --transport stdio

# 自定义参数
uv run x-QiuChi --host 127.0.0.1 --port 8080 --log-level DEBUG

# 查看帮助
uv run x-QiuChi --help
```

#### 方式二：uv run 直接启动

```bash
# HTTP 模式（默认，端口 8888）
uv run python -m src.main

# Stdio 模式（兼容 Claude Desktop）
uv run python -m src.main --transport stdio

# 自定义参数
uv run python -m src.main --host 127.0.0.1 --port 8080 --log-level DEBUG
```

#### 方式三：Docker 容器部署

```bash
# 构建并启动
docker compose up -d --build

# 查看日志
docker compose logs -f

# 停止
docker compose down
```

### 6. 常用工程命令

```bash
# 运行全部测试（内置 coverage 门禁：--cov=src --cov-fail-under=45）
uv run pytest

# 运行指定测试文件（详细输出）
uv run pytest tests/test_protocol.py -v

# 测试覆盖率报告
uv run pytest --cov=src --cov-report=term-missing tests/

# 代码格式化
uv run ruff format src/

# 代码静态检查
uv run ruff check src/

# 自动修复可修复的 lint 问题
uv run ruff check --fix src/ tests/

# 类型检查
uv run mypy src/

# 构建 wheel 与 sdist
uv build

# MCP Inspector 验证
npx @anthropic-ai/mcp-inspector
# 连接地址: http://localhost:8888/mcp
```

> **提交前自动检查**：仓库已配置 git pre-commit 钩子（`hooks/pre-commit`），每次 `git commit` 前自动执行：
>
> ```sh
> uv run ruff check --fix src/ tests/
> uv run ruff format src/ tests/
> ```
>
> 能自动修复的问题会被自动修复并重新暂存；无法自动修复的会阻止提交（可用 `git commit --no-verify` 临时跳过）。克隆仓库后首次启用：`git config core.hooksPath hooks`

### 7. 认证与可观测性

#### 传输层认证（Bearer Token）

认证挂在 MCP **HTTP 传输层**（mcp SDK 官方 `RequireAuthMiddleware`），能读取真实 `Authorization` 请求头，对所有 `/mcp` 请求生效（无 token / 错误 token 返回 `401 invalid_token`）。

```bash
# 方式一：YAML 配置（config.yaml）
# middleware:
#   auth:
#     enabled: true
#     tokens: ["my-secret-token"]

# 方式二：环境变量（推荐，避免明文入库）
AUTH_ENABLED=true AUTH_TOKENS="my-secret-token" uv run python -m src.main
```

开启认证后所有 MCP 客户端请求需携带：

```http
Authorization: Bearer my-secret-token
```

Docker 部署时若开启认证，请同步设置 `MCP_AUTH_TOKEN`（健康检查会自动携带）：

```yaml
# docker-compose.yml
environment:
  AUTH_ENABLED: "true"
  AUTH_TOKENS: "my-secret-token"
  MCP_AUTH_TOKEN: "my-secret-token"
```

#### OpenTelemetry 可观测性

框架内置 OpenTelemetry：每个 HTTP 请求注入真实 `request_id`（`X-Request-ID` 或自动生成），贯穿结构化日志；并记录 HTTP 请求 span 与请求计数/耗时指标。

| exporter | 行为 | 适用场景 |
|---------|------|---------|
| `console`（默认） | span 输出到控制台 | 本地开发 |
| `otlp` | 通过 OTLP/HTTP 导出 trace + metrics | 生产接入 Jaeger / OTel Collector 等 |

```bash
TELEMETRY_ENABLED=true TELEMETRY_EXPORTER=otlp \
TELEMETRY_OTLP_ENDPOINT=http://localhost:4318/v1/traces \
uv run python -m src.main
```

---

## 工程规范

### 版本管理（单一事实源）

版本号**唯一事实源为 `pyproject.toml` 的 `version` 字段**（当前 `0.1.0`）。启动时通过 `importlib.metadata` 自动读取，MCP 握手 `serverInfo.version`、CLI 输出版本号均与其一致。**不要在 `config.yaml` 中配置 `mcp.version`**（如需临时覆盖可设置 `--version` CLI 参数）。

### 提交规范（Conventional Commits）

提交信息遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```text
feat: 新增功能
fix: 修复缺陷
docs: 文档变更
refactor: 重构（无行为变化）
test: 测试变更
chore: 构建/依赖/工具链变更
ci: CI 配置变更
perf: 性能优化
```

示例：`fix: 修复认证中间件未注入真实 request_id 的问题`

**本地强制校验（commit-msg 钩子）**：仓库自带 `hooks/commit-msg`（经 `core.hooksPath` 生效），每次提交自动校验信息格式——`<type>[optional scope]: <subject>`，type 必须是上述枚举之一，subject 不超过 100 字符。合并/还原提交（`Merge` / `Revert` / `fixup!` / `squash!` 开头）自动放行。校验脚本为 `scripts/check_commit_msg.py`（纯标准库，无需额外安装）。临时跳过：`git commit --no-verify`。

### CI/CD

仓库内置 GitHub Actions（`.github/workflows/ci.yml`），push 到 `main`/`master` 或 PR 时自动执行：

1. **lint** —— `ruff check` + `ruff format --check`（src/ 与 tests/）
2. **typecheck** —— `mypy src/`
3. **test** —— `pytest`（内置 coverage 门禁 `--cov-fail-under=45`）
4. **build** —— `uv build` 产出 wheel 与 sdist，并上传 artifact

### 8. 使用方法示例

#### 装饰器注册工具

```python
from src.main import create_server, tool, resource, prompt

server = create_server("MyServer")

# 注册工具
@tool(category="math")
def add(a: float, b: float) -> float:
    """两数相加"""
    return a + b

# 注册资源
@resource(name="config://app", category="config")
def get_app_config() -> str:
    """获取应用配置"""
    return '{"version": "1.0.0"}'

# 注册提示词
@prompt(category="code")
def code_review(language: str) -> str:
    """生成代码审查提示词"""
    return f"请审查以下 {language} 代码的最佳实践。"

server.run()
```

#### HTTP 客户端调用

```python
import httpx

# 获取 Session ID
resp = httpx.get("http://localhost:8888/mcp",
                 headers={"Accept": "text/event-stream"})
session_id = resp.headers.get("mcp-session-id")

# 调用工具
resp = httpx.post(
    "http://localhost:8888/mcp",
    json={"jsonrpc": "2.0", "method": "tools/call",
          "params": {"name": "add", "arguments": {"a": 10, "b": 20}},
          "id": 1},
    headers={"Content-Type": "application/json",
             "mcp-session-id": session_id}
)
print(resp.json())  # {"result": {"content": [{"text": "30.0"}]}}
```

#### LangChain / LangGraph 集成

```python
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent

client = MultiServerMCPClient({
    "qiuchi_mcp": {
        "transport": "http",
        "url": "http://localhost:8888/mcp",
    }
})

tools = await client.get_tools()
model = init_chat_model("openai:gpt-4o-mini")
agent = create_react_agent(model, tools)

response = await agent.ainvoke({"messages": "计算 123 + 456"})
print(response['messages'][-1].content)
```

---

## 项目结构

```
x-QiuChi/
├── config.yaml                      # 运行时配置文件
├── config.yaml.example              # 配置示例（含全部字段说明）
├── pyproject.toml                   # 包配置、依赖声明、工具链设置
├── Dockerfile                       # 多阶段构建镜像定义
├── docker-compose.yml               # 容器编排配置
├── LICENSE                          # MIT 开源许可证
│
├── src/                             # 源码根目录
│   ├── main.py                      # 主入口：CLI 参数解析与服务器启动
│   │
│   ├── constants/                   # 常量定义层
│   │   ├── constants.py             # 全局常量（应用信息、环境标识、配置文件）
│   │   └── enums.py                 # 全局枚举（Environment、LogLevel、TransportType、LogOutput、ServerState、PluginType、PluginStatus）
│   │
│   ├── core/                        # 核心层：框架基础设施
│   │   ├── config.py                # Settings 配置管理（dataclass 分节，环境变量 > YAML > 默认值，validate/reload）
│   │   ├── logger.py                # loguru 结构化日志封装（文件轮转、敏感信息过滤）
│   │   ├── middleware.py            # 中间件管道（ErrorHandler / Logging）
│   │   ├── auth.py                  # 传输层认证（SimpleTokenVerifier，mcp TokenVerifier Protocol）
│   │   └── opentelemetry.py         # OpenTelemetry（request_id 注入、HTTP span/metrics，console/otlp）
│   │
│   ├── plugins/                     # 插件层：插件系统核心
│   │   ├── base.py                  # 插件抽象基类与元数据定义（PluginMetadata）
│   │   ├── registry.py              # PluginRegistry 统一注册表（RLock 线程安全）
│   │   ├── manager.py               # PluginManager 插件管理器（自动发现、依赖解析、生命周期）
│   │   ├── discovery.py             # 插件发现扫描器
│   │   ├── loader.py                # 插件加载器
│   │   └── collector.py             # 插件收集器（装饰器注册入口）
│   │
│   ├── server/                      # 服务层：MCP 服务器核心
│   │   ├── server.py                # MCPServer 编排门面（组装 FastMCP / 认证 / 中间件 / 插件 / 生命周期）
│   │   └── lifecycle.py             # 服务器生命周期状态机（UNINITIALIZED → RUNNING → STOPPED）
│   │
│   ├── runtime/                     # 运行时层：请求上下文与会话管理
│   │   ├── context.py               # RequestContext 请求上下文
│   │   └── session.py               # SessionManager 会话管理器
│   │
│   ├── transport/                   # 传输层：多协议传输抽象
│   │   └── transport.py             # 传输配置与服务承载（Stdio / SSE / Streamable-HTTP，默认 streamable-http）
│   │
│   ├── utils/                       # 工具层（当前为空，预留通用辅助函数位）
│   │
│   └── extensions/                  # 扩展层：内置扩展插件（tools / resources / prompts）
│       ├── tools/
│       │   └── math.py              # 8 个数学工具（加减乘除、幂、开方、温度转换）
│       ├── resources/
│       │   └── config.py            # 3 个配置资源（server config / version / API docs）
│       └── prompts/
│           └── templates.py         # 5 个提示词模板（问候、代码审查、天气穿搭等）
│
├── examples/                        # 外部示例代码
│   ├── mcp_clients/
│   │   ├── mcp_client.py            # 原生 JSON-RPC MCP 客户端示例
│   │   └── langchain_mcp_client.py  # LangChain MCP 集成示例
│   └── mcp_servers/
│       └── weather_mcp_server.py    # OpenWeatherMap 天气 MCP 服务示例
│
├── tests/                           # 测试目录
│   ├── test_integration.py          # 6 步集成测试套件
│   ├── test_protocol.py             # 真实 MCP 协议测试（官方 client）与传输层认证测试
│   ├── test_config.py               # 配置单测（版本单一源 / 环境变量覆盖）
│   ├── test_auth.py                 # 认证单测
│   ├── test_telemetry.py            # 可观测性单测
│   ├── test_runtime.py              # 运行时上下文单测
│   └── test_main_cli.py             # CLI 入口单测
│
├── .github/workflows/ci.yml         # CI：lint + mypy + test（coverage 门禁）+ build
│
├── docs/                            # 文档目录
├── scripts/                         # 脚本工具目录
├── static/                          # 静态资源目录
├── logs/                            # 日志输出目录（运行时生成）
└── tmp/                             # 临时文件目录
```

---

## 系统架构

### 系统分层架构图

```mermaid
flowchart TD
    A["MCP 客户端<br/>(Claude Desktop / LangChain / 自定义客户端)"]
    B["传输层 transport<br/>Stdio / SSE / Streamable-HTTP（默认）"]
    B1["传输层加固（HTTP 模式）<br/>Bearer Token 认证（RequireAuthMiddleware）+ OpenTelemetry 遥测"]
    C["中间件管道 core.middleware<br/>ErrorHandler → Logging → 业务处理器"]
    subgraph D["MCP 三大原语（PluginType）"]
        direction LR
        D1["Tools（工具）"]
        D2["Resources（资源）"]
        D3["Prompts（提示词）"]
    end
    E["插件系统 plugins<br/>装饰器收集 → 发现 → 加载/启用 → 统一注册"]
    F["PluginRegistry 统一注册表<br/>(RLock 线程安全)"]
    G["MCPServer 编排门面 server<br/>组装 FastMCP，LifecycleManager 显式状态机"]
    H["core 基础设施<br/>Settings 配置 / loguru 日志 / 中间件 / 认证 / 遥测"]
    I["constants 共享类型<br/>TransportType / ServerState / PluginType 等枚举"]

    A -->|"MCP 协议（JSON-RPC）"| B
    B --> B1
    B1 --> C
    C --> D
    E -->|"注册"| D
    E --> F
    G -->|"编排"| E
    G --> H
    H --> I
```

### 服务器启动流程

```mermaid
flowchart TD
    S1["解析 CLI 参数 / 加载配置<br/>（main.py + Settings）"] --> S2["创建 MCPServer 实例<br/>装配 FastMCP / 传输层认证 / 默认中间件管道"]
    S2 --> S3["生命周期状态机<br/>UNINITIALIZED → READY → RUNNING"]
    S3 --> S4["插件初始化（PluginManager）<br/>发现 → 加载 → 启用"]
    S4 --> S5["装饰器函数注册<br/>包装中间件管道后写入 PluginRegistry + FastMCP"]
    S5 --> S6["serve_mcp 阻塞监听<br/>Streamable-HTTP（默认） / SSE / Stdio"]
```

### 请求处理流程

```mermaid
flowchart TD
    R1["接收 MCP 请求（JSON-RPC）"] --> R2["HTTP 传输层<br/>Bearer Token 认证 + OpenTelemetry 埋点（request_id）"]
    R2 --> R3["FastMCP 按 method 分发<br/>到已注册的工具 / 资源 / 提示词"]
    R3 --> R4["中间件管道<br/>ErrorHandler → Logging"]
    R4 --> R6["执行业务函数<br/>（RequestContext 贯穿管道）"]
    R6 --> R9["返回 MCP 响应"]
```

### 模块依赖关系图

```mermaid
flowchart TD
    A["src/main.py<br/>主入口"] --> B["src/server/server.py<br/>MCPServer 编排门面"]
    A --> K["src/core/logger.py<br/>日志系统"]
    K --> K1["loguru（外部依赖）"]

    B --> C1["FastMCP（外部依赖）"]
    B --> D["src/plugins/manager.py<br/>插件管理器"]
    B --> E["src/core/middleware.py<br/>中间件管道"]
    B --> F["src/transport/transport.py<br/>传输承载"]
    B --> AUTH["src/core/auth.py<br/>传输层认证装配"]
    B --> LC["src/server/lifecycle.py<br/>生命周期状态机"]
    B --> H["src/core/config.py<br/>配置管理"]
    H --> H1["dataclass + PyYAML（外部依赖）"]

    D --> D1["src/plugins/base.py<br/>插件基类"]
    D --> D2["src/plugins/registry.py<br/>PluginRegistry"]
    D --> D3["src/plugins/discovery.py<br/>插件发现"]
    D --> D4["src/plugins/collector.py<br/>装饰器收集"]

    E --> E1["ErrorHandler 中间件"]
    E --> E2["Logging 中间件"]

    F --> T1["src/constants/enums.py<br/>TransportType 枚举"]
    F --> T2["uvicorn（外部依赖）"]
    F -.->|"延迟导入"| OT["src/core/opentelemetry.py<br/>遥测埋点"]

    D4 --> EN["src/constants/<br/>枚举与常量（最底层）"]
    T1 --> EN
```

---

## 技术栈

| 分类 | 技术 | 版本 | 说明 |
|------|------|------|------|
| **开发语言** | [Python](https://www.python.org/) | >= 3.11 | 主开发语言 |
| **MCP 框架** | [FastMCP (mcp)](https://github.com/modelcontextprotocol/python-sdk) | >= 1.0.0, < 2.0.0 | MCP 协议 Python SDK，服务器核心 |
| **数据验证** | [Pydantic](https://docs.pydantic.dev/) | >= 2.0.0 | 传输层配置模型（SSEConfig / HTTPConfig / TLSConfig）与数据验证 |
| **HTTP 客户端** | [httpx](https://www.python-httpx.org/) | >= 0.27.0 | 异步 HTTP 客户端 |
| **配置解析** | [PyYAML](https://pyyaml.org/) | >= 6.0 | YAML 配置文件解析 |
| **日志** | [loguru](https://loguru.readthedocs.io/) | >= 0.7.0 | 结构化日志，文件轮转与敏感信息过滤 |
| **代码质量** | [Ruff](https://docs.astral.sh/ruff/) | >= 0.6.0 | 代码格式化 + Lint（替代 Black + Flake8） |
| **类型检查** | [Mypy](https://mypy.readthedocs.io/) | >= 1.0.0 | 静态类型检查（strict 模式） |
| **测试框架** | [Pytest](https://docs.pytest.org/) + pytest-asyncio | >= 8.0.0 | 单元测试与异步测试 |
| **包管理** | [uv](https://docs.astral.sh/uv/) | >= 0.1 | 高性能 Python 包管理器 |
| **容器化** | [Docker](https://www.docker.com/) / Docker Compose | - | 多阶段构建，非 root 用户运行，健康检查 |
| **构建后端** | [Hatchling](https://hatch.pypa.io/) | - | PEP 517 构建后端 |

---

## API 文档说明

秋池（QiuChi）作为 MCP 服务器框架，不提供传统 REST API，而是通过 **MCP 协议** 进行能力发现与交互。

### MCP 协议接口清单

| 能力 | MCP 方法 | 说明 |
|------|---------|------|
| 工具列表 | `tools/list` | 获取所有已注册工具及其参数定义 |
| 工具调用 | `tools/call` | 调用指定工具并返回执行结果 |
| 资源列表 | `resources/list` | 获取所有已注册资源及其 URI |
| 资源读取 | `resources/read` | 读取指定 URI 的资源内容 |
| 提示词列表 | `prompts/list` | 获取所有已注册提示词模板 |
| 提示词获取 | `prompts/get` | 获取指定提示词模板及其参数 |

### 内置示例

**工具（8 个）**：

| 工具名 | 说明 |
|--------|------|
| `add` | 两数相加 |
| `subtract` | 两数相减 |
| `multiply` | 两数相乘 |
| `divide` | 两数相除 |
| `power` | 幂运算 |
| `sqrt` | 开平方 |
| `celsius_to_fahrenheit` | 摄氏度转华氏度 |
| `fahrenheit_to_celsius` | 华氏度转摄氏度 |

**资源（3 个）**：

| 资源 URI | 说明 |
|----------|------|
| `config://server` | 服务器配置信息 |
| `config://version` | 版本信息 |
| `docs://api` | API 文档 |

**提示词（5 个）**：

| 提示词名 | 说明 |
|----------|------|
| `greeting` | 个性化问候 |
| `code_review` | 代码审查提示词 |
| `weather_outfit_advice` | 天气穿搭建议 |
| `explain_concept` | 概念解释提示词 |
| `summarize_document` | 文档摘要提示词 |

---

## 存储配置说明

### 内存存储

| 存储类型 | 实现方式 | 配置位置 | 说明 |
|---------|---------|---------|------|
| 会话存储 | 内存字典 | `src/runtime/session.py` | SessionManager，支持 TTL 和自动清理 |
| 插件注册表 | 内存字典 | `src/plugins/registry.py` | PluginRegistry，线程安全（RLock） |

### 日志文件存储

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `logging.file_path` | `logs/x-QiuChi_{time:YYYY-MM-DD-HH}.log` | 日志文件路径（支持时间模板变量） |
| `logging.rotation` | `1 hour` | 日志轮转周期 |
| `logging.retention` | `7 days` | 日志保留时长 |
| `logging.output` | `both` | 输出目标：`stderr`（仅标准错误）/ `file`（仅文件）/ `both`（两者） |

---

## 许可证

本项目采用 [MIT](LICENSE) 许可证。

---

## 参考资料

| 资源 | 链接 |
|------|------|
| MCP 协议规范 | https://modelcontextprotocol.io/ |
| FastMCP SDK | https://github.com/modelcontextprotocol/python-sdk |
| Python 官方文档 | https://docs.python.org/3.11/ |
| Pydantic 文档 | https://docs.pydantic.dev/ |
| uv 包管理器 | https://docs.astral.sh/uv/ |
| loguru 日志库 | https://loguru.readthedocs.io/ |
| httpx 文档 | https://www.python-httpx.org/ |
| PyYAML 文档 | https://pyyaml.org/wiki/PyYAMLDocumentation |
| Ruff 文档 | https://docs.astral.sh/ruff/ |
| Mypy 文档 | https://mypy.readthedocs.io/ |
| Pytest 文档 | https://docs.pytest.org/ |
| Docker 官方文档 | https://docs.docker.com/ |
| Hatchling 文档 | https://hatch.pypa.io/ |

---

## 联系方式

| 渠道 | 信息 |
|------|------|
| 作者 | John Young（夜雨诗来） |
| 邮箱 | [john.young@foxmail.com](mailto:john.young@foxmail.com) |
| Gitee | https://gitee.com/yeyushilai |
| GitHub | https://github.com/yeyushilai |
| 项目地址 | https://github.com/chain-engine/x-QiuChi |
