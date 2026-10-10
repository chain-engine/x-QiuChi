# 使用 Python 3.11 作为基础镜像
FROM python:3.11-slim AS builder

# 安装 uv 包管理器（使用国内 PyPI 镜像加速）
RUN pip install uv -i https://mirrors.aliyun.com/pypi/simple/

# 设置工作目录
WORKDIR /app

# 复制项目文件
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY config.yaml ./

# 使用 uv 安装依赖到虚拟环境（依赖下载同样走镜像源）
ENV UV_INDEX_URL="https://mirrors.aliyun.com/pypi/simple/"
RUN uv venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
RUN uv pip install --python /app/venv/bin/python -r pyproject.toml

# 生产阶段
FROM python:3.11-slim

# 创建非 root 用户
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 设置工作目录
WORKDIR /app

# 从构建阶段复制虚拟环境
COPY --from=builder /app/venv /app/venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/config.yaml /app/config.yaml

# 设置环境变量
ENV PATH="/app/venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV MCP_TRANSPORT="streamable-http"
ENV MCP_HOST="0.0.0.0"
ENV MCP_PORT="8888"
ENV LOGGING_LEVEL="INFO"
ENV LOGGING_OUTPUT="both"

# 创建日志目录并设置权限
RUN mkdir -p /app/logs && chown -R appuser:appuser /app/logs

# 切换用户
USER appuser

# 暴露端口
EXPOSE 8888

# 健康检查（compose 中可被覆盖；默认做一次真实的 MCP initialize 握手并校验 200）
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx, sys; r = httpx.post('http://localhost:8888/mcp', json={'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'healthcheck','version':'1.0'}}}, headers={'Accept':'application/json, text/event-stream'}, timeout=5); sys.exit(0 if r.status_code == 200 else 1)"

# 启动命令
CMD ["python", "-m", "src.main"]