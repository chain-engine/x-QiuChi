"""
汉江管理系统 MCP 适配器（HTTP 转接代理）

将汉江管理系统后端（/api/admin/v1/*）转接为 MCP 工具，业务零侵入：
- client：HanJiangClient（RSA 登录 / token 生命周期 / 统一请求封装）
- auth_tools：认证域工具（hanjiang_login / hanjiang_logout / hanjiang_session_info）
- user_tools：用户管理域工具（create / list / get / update / status / reset_password / delete）

接入范围约定：仅接入汉江 admin 管理系统（/api/admin/v1/*）。
开放 API（/api/open/v1/*）与开放平台门户（/api/open/portal/*）明确不接入，
如需扩展须先与业务方确认。

工具定义原则：工具为**人工精选映射**（非 OpenAPI 全量抽象），
仅暴露 Agent 完成业务所需的最小能力面——有 OpenAPI 不代表所有端点都要
变成工具；认证时序（RSA 登录 / token 生命周期）由本适配器封装，模型不接触。

装配方式：应用入口显式 import 本包（src/main.py 的 main_async 中
import src.adapters），import 副作用触发 @tool 收集，
随后由 PluginManager.initialize() 统一注册进 registry + FastMCP。
"""

from src.adapters.hanjiang import auth_tools, user_tools  # noqa: F401  # 触发装饰器收集
from src.adapters.hanjiang.client import (
    HanJiangClient,
    HanJiangError,
    get_client,
    reset_client,
)

__all__ = [
    "HanJiangClient",
    "HanJiangError",
    "get_client",
    "reset_client",
    "auth_tools",
    "user_tools",
]
