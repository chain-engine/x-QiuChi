# 使用 Python 3.11 作为基础镜像
FROM python:3.11-slim AS builder

# 安装 uv 包管理器
RUN pip install uv

# 设置工作目录
WORKDIR /app

# 复制项目文件
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY config.yaml ./

# 使用 uv 安装依赖到虚拟环境
RUN uv venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
RUN uv pip install --system -r pyproject.toml

# 生产阶段
FROM python:3.11-slim

# 安装运行时依赖（如果需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

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
ENV PYTHONPATH="/app/src"
ENV MCP_TRANSPORT="streamable-http"
ENV MCP_HOST="0.0.0.0"
ENV MCP_PORT="8000"
ENV MCP_LOG_LEVEL="INFO"
ENV MCP_LOG_OUTPUT="both"

# 创建日志目录并设置权限
RUN mkdir -p /app/logs && chown -R appuser:appuser /app/logs

# 切换用户
USER appuser

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/mcp', headers={'Accept': 'text/event-stream'}, timeout=5)" || exit 1

# 启动命令
CMD ["python", "src/main.py"]