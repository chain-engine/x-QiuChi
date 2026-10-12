"""
汉江认证域 MCP 工具

将汉江管理系统认证 API（登录 / 登出 / 当前用户）转接为 MCP 工具。
所有工具经 @tool 收集，注册后由 FastMCP 暴露给 MCP 客户端。

安全约定：
- 密码等敏感参数由 LoggingMiddleware 的 _SENSITIVE_FIELDS 自动脱敏，不入日志
- 返回统一为美化 JSON 文本（模型可直接读取）；错误返回"原因 + 建议"
"""

from __future__ import annotations

import json
from typing import Any

from src.adapters.hanjiang.client import HanJiangError, get_client
from src.plugins import tool


def _format_result(data: Any) -> str:
    """将汉江响应 data 格式化为美化 JSON 文本。"""
    return json.dumps(data, ensure_ascii=False, indent=2)


@tool(category="hanjiang.auth", subcategory="session", tags=["hanjiang", "auth", "login"])
async def hanjiang_login(username: str, password: str) -> str:
    """
    登录汉江管理系统（密码经 RSA-OAEP 加密传输，password 参数自动脱敏不入日志）

    Args:
        username: 汉江账号（用户名/手机号/邮箱）
        password: 明文密码（仅本次调用使用，不落日志）

    Returns:
        登录结果：访问令牌有效期与令牌对概要
    """
    try:
        data = await get_client().login(username, password)
        return _format_result(
            {
                "token_type": data.get("token_type", "Bearer"),
                "expires_in": data.get("expires_in"),
                "message": "登录成功",
            }
        )
    except HanJiangError as e:
        return f"登录失败: {e.message}（请检查账号密码或稍后重试）"


@tool(category="hanjiang.auth", subcategory="session", tags=["hanjiang", "auth", "logout"])
async def hanjiang_logout() -> str:
    """
    登出汉江管理系统：清除当前会话在汉江的登录态，使令牌立即失效

    Returns:
        登出结果
    """
    try:
        data = await get_client().logout()
        return _format_result(data)
    except HanJiangError as e:
        return f"登出失败: {e.message}"


@tool(category="hanjiang.auth", subcategory="session", tags=["hanjiang", "auth", "session", "me"])
async def hanjiang_session_info() -> str:
    """
    获取汉江当前登录用户资料（含角色与权限码），用于验证会话有效性与权限边界

    Returns:
        当前登录用户信息（id / username / name / role_code / permissions / status 等）
    """
    try:
        data = await get_client().get_current_user()
        return _format_result(data)
    except HanJiangError as e:
        return f"获取会话信息失败: {e.message}（会话可能已过期，可重新登录）"


__all__ = ["hanjiang_login", "hanjiang_logout", "hanjiang_session_info"]
