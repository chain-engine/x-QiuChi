"""
QiuChi 插件包

提供统一的插件装饰器和插件基类。
"""

from .base import (
    tool,
    resource,
    prompt,
    create_plugin_decorator,
    PluginDecorator,
    get_tool_decorator,
    get_resource_decorator,
    get_prompt_decorator,
)

__all__ = [
    "tool",
    "resource",
    "prompt",
    "create_plugin_decorator",
    "PluginDecorator",
    "get_tool_decorator",
    "get_resource_decorator",
    "get_prompt_decorator",
]