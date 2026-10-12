"""
适配器包：外部系统集成（HTTP 转接代理）

承载"将外部系统 REST API 转接为 MCP 工具"的系统集成层，与插件机制解耦：
- 不参与 plugins 自动发现（discovery_paths 只扫 src.plugins.builtin）
- 由应用装配点显式 import（src/main.py 启动时 import 本包触发装饰器收集）
- 工具装饰器照用 plugins 公共 API（from src.plugins import tool_decorator）

当前适配器：
- hanjiang：汉江管理系统（认证 + 用户管理）
"""

from src.adapters import hanjiang  # noqa: F401  # 装配全部适配器（触发 @tool_decorator 收集）

__all__ = ["hanjiang"]
