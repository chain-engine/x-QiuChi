#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LangChain MCP 客户端示例

使用 langchain_mcp_adapters 连接 QiuChi 服务器，
展示 LangChain/LangGraph 用户如何接入 MCP 服务。

安装依赖：
    pip install langchain-mcp-adapters langgraph "langchain[openai]"

环境变量：
    export OPENAI_API_KEY=your_api_key

运行方式：
    # HTTP 模式（需要先启动 MCP 服务器）
    python langchain_mcp_client.py --mode http

    # Stdio 模式（自动启动 MCP 服务器）
    python langchain_mcp_client.py --mode stdio

参考文档：
    - https://pypi.org/project/langchain-mcp-adapters/
    - https://docs.langchain.com/oss/python/langchain/mcp
"""

import asyncio
import argparse
import os
import sys
from pathlib import Path

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
SRC_PATH = PROJECT_ROOT / "src"


async def create_http_client():
    """
    创建 HTTP 模式的 MCP 客户端。

    适用于已部署的 MCP 服务器，通过 HTTP/SSE 连接。
    """
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(
        {
            "qiuchi_mcp": {
                "transport": "http",
                "url": "http://localhost:8000/mcp",
            }
        }
    )
    return client


async def create_stdio_client():
    """
    创建 Stdio 模式的 MCP 客户端。

    适用于本地开发，自动启动 MCP 服务器进程。
    """
    from langchain_mcp_adapters.client import MultiServerMCPClient

    # 获取 Python 解释器路径
    python_path = sys.executable

    # MCP 服务器路径
    server_path = str(SRC_PATH / "main.py")

    client = MultiServerMCPClient(
        {
            "qiuchi_mcp": {
                "transport": "stdio",
                "command": python_path,
                "args": [server_path],
                "env": {
                    "PYTHONPATH": str(SRC_PATH),
                    "MCP_TRANSPORT": "stdio",
                }
            }
        }
    )
    return client


async def run_simple_agent(client, query: str):
    """
    使用 LangGraph 的 create_react_agent 运行查询。

    Args:
        client: MultiServerMCPClient 实例
        query: 用户查询
    """
    from langchain.chat_models import init_chat_model
    from langgraph.prebuilt import create_react_agent

    # 获取 MCP 工具
    tools = await client.get_tools()

    print(f"\n{'='*60}")
    print(f"可用工具: {[tool.name for tool in tools]}")
    print(f"{'='*60}\n")

    # 创建 ReAct Agent（需要 OPENAI_API_KEY）
    model = init_chat_model("openai:gpt-4o-mini")
    agent = create_react_agent(model, tools)

    # 运行查询
    print(f"查询: {query}")
    print("-" * 60)

    response = await agent.ainvoke({"messages": query})

    print(f"回答: {response['messages'][-1].content}")
    return response


async def run_langgraph_agent(client, query: str):
    """
    使用 LangGraph StateGraph 运行查询。

    Args:
        client: MultiServerMCPClient 实例
        query: 用户查询
    """
    from langchain.chat_models import init_chat_model
    from langgraph.graph import StateGraph, MessagesState, START
    from langgraph.prebuilt import ToolNode, tools_condition

    # 获取 MCP 工具
    tools = await client.get_tools()

    print(f"\n{'='*60}")
    print(f"可用工具: {[tool.name for tool in tools]}")
    print(f"{'='*60}\n")

    # 初始化模型
    model = init_chat_model("openai:gpt-4o-mini")

    # 定义调用模型的节点
    def call_model(state: MessagesState):
        response = model.bind_tools(tools).invoke(state["messages"])
        return {"messages": response}

    # 构建图
    builder = StateGraph(MessagesState)
    builder.add_node("call_model", call_model)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "call_model")
    builder.add_conditional_edges("call_model", tools_condition)
    builder.add_edge("tools", "call_model")

    graph = builder.compile()

    # 运行查询
    print(f"查询: {query}")
    print("-" * 60)

    response = await graph.ainvoke({"messages": query})

    print(f"回答: {response['messages'][-1].content}")
    return response


async def demo_tools_list(client):
    """
    演示列出所有可用工具。
    """
    from langchain_mcp_adapters.tools import load_mcp_tools

    async with client.session("qiuchi_mcp") as session:
        tools = await load_mcp_tools(session)

        print("\n" + "=" * 60)
        print("QiuChi 可用工具列表")
        print("=" * 60)

        for i, tool in enumerate(tools, 1):
            print(f"\n{i}. {tool.name}")
            print(f"   描述: {tool.description[:80]}...")
            if hasattr(tool, 'args_schema') and tool.args_schema:
                schema = tool.args_schema.schema()
                props = schema.get('properties', {})
                if props:
                    print(f"   参数: {list(props.keys())}")


async def main():
    parser = argparse.ArgumentParser(description="LangChain MCP 客户端示例")
    parser.add_argument(
        "--mode",
        choices=["http", "stdio"],
        default="http",
        help="连接模式: http (连接已有服务器) 或 stdio (自动启动服务器)"
    )
    parser.add_argument(
        "--demo",
        choices=["simple", "langgraph", "list"],
        default="simple",
        help="演示模式: simple (简单Agent), langgraph (StateGraph), list (仅列出工具)"
    )
    parser.add_argument(
        "--query",
        default="请计算 123 加 456 等于多少？",
        help="测试查询"
    )

    args = parser.parse_args()

    # 检查环境变量
    if args.demo != "list" and not os.environ.get("OPENAI_API_KEY"):
        print("错误: 请设置 OPENAI_API_KEY 环境变量")
        print("  export OPENAI_API_KEY=your_api_key")
        sys.exit(1)

    # HTTP 模式提示
    if args.mode == "http":
        print("提示: HTTP 模式需要先启动 MCP 服务器")
        print("  PYTHONPATH=src uv run python src/main.py")
        print()

    # 创建客户端
    if args.mode == "http":
        client = await create_http_client()
    else:
        client = await create_stdio_client()

    # 运行演示
    if args.demo == "list":
        await demo_tools_list(client)
    elif args.demo == "simple":
        await run_simple_agent(client, args.query)
    elif args.demo == "langgraph":
        await run_langgraph_agent(client, args.query)


if __name__ == "__main__":
    asyncio.run(main())
