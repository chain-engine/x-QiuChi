"""
插件系统（注册表体系）

架构：PluginManager（门面）串联三个互不感知的组件——
PluginDiscovery（发现）→ PluginCollector（收集）→ PluginRegistry（注册），
MCPServer 只需与 PluginManager 对话，不直接触碰各组件。

生命周期（装饰器插件：发现 → 收集 → 注册 → 调用）
--------------------------------------------------
① 发现（server.start() → initialize() → discover_plugins()）
   PluginDiscovery 扫描 discovery_paths
       │ import 子模块，触发装饰器收集
       ▼
   返回插件名单

② 收集（模块 import 时，装饰器副作用）
   业务代码: @tool / @resource / @prompt 标记函数
       │ 装饰器 collect() 自动写入（无需显式调用）
       ▼
   PluginCollector（全局单例，进程内唯一）

③ 注册（initialize() → _register_decorator_functions()）
   get_*_collector().get_items()
       ▼
   _register_item(item_type, name, info)
       ├─► _build_middleware_wrapper()：包裹中间件管道（注入 request_id）
       ├─► registry.register_<item_type>()：写入 ServerRegistry
       └─► mcp.<item_type>()(wrapper)：注册进 FastMCP

④ 调用（运行时）
   MCP 客户端 ──► FastMCP ──► wrapper（保持原签名）
       │ 构造 RequestContext（method / request_id / params）
       ▼
   middleware_chain.execute(req, final_handler)
       │ ErrorHandler → Logging → 原函数
       ▼
   返回结果

组件职责：
- PluginDiscovery（发现）：扫描 discovery_paths 并导入模块，触发装饰器收集
- PluginCollector（收集）：进程级全局单例，装饰器在模块 import 时自动收集函数
- PluginRegistry（注册）：统一注册表（工具/资源/提示词 + 元数据），挂在 server.registry
- PluginManager（门面）：发现编排 + 注册分发
"""

from .collector import (
    PluginCollector,
    get_prompt_collector,
    get_resource_collector,
    get_tool_collector,
    prompt,
    resource,
    tool,
)
from .discovery import PluginDiscovery, discover_plugins
from .manager import PluginManager
from .registry import PluginMetadata, PluginRegistry, PluginType, global_registry

__all__ = [
    # 基础类型
    "PluginMetadata",
    # 装饰器 & 收集器
    "tool",
    "resource",
    "prompt",
    "get_tool_collector",
    "get_resource_collector",
    "get_prompt_collector",
    "PluginCollector",
    # 注册表
    "PluginRegistry",
    "PluginType",
    "global_registry",
    # 发现
    "PluginDiscovery",
    "discover_plugins",
    # 管理器
    "PluginManager",
]
