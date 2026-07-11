"""
QiuChi 传输层实现

增强的传输配置系统，支持：
- 多种传输方式
- 连接池配置
- 超时设置
- TLS/SSL 支持
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union
from pydantic import BaseModel, Field

# 从共享类型模块导入
from core.types import TransportType
from core.config.config import settings


class SSEConfig(BaseModel):
    """SSE 传输配置"""
    ping_interval: int = Field(default=30, description="心跳间隔（秒）")
    max_connections: int = Field(default=100, description="最大连接数")
    retry_timeout: int = Field(default=3000, description="重连超时时间（毫秒）")


class HTTPConfig(BaseModel):
    """HTTP 传输配置"""
    max_body_size: int = Field(default=10 * 1024 * 1024, description="最大请求体大小（字节）")
    request_timeout: int = Field(default=30, description="请求超时时间（秒）")
    keepalive_timeout: int = Field(default=5, description="Keep-Alive 超时时间（秒）")
    cors_enabled: bool = Field(default=True, description="是否启用 CORS")
    cors_origins: list[str] = Field(default_factory=lambda: ["*"], description="CORS 允许的源")
    compression_enabled: bool = Field(default=True, description="是否启用压缩")


class TLSConfig(BaseModel):
    """TLS/SSL 配置"""
    enabled: bool = Field(default=False, description="是否启用 TLS")
    cert_file: Optional[str] = Field(default=None, description="证书文件路径")
    key_file: Optional[str] = Field(default=None, description="私钥文件路径")
    ca_file: Optional[str] = Field(default=None, description="CA 证书文件路径")
    verify_client: bool = Field(default=False, description="是否验证客户端证书")


@dataclass
class TransportConfig:
    """
    传输层配置

    根据传输类型生成 FastMCP.run() 所需的参数，支持高级配置。
    """

    transport: TransportType = TransportType.STREAMABLE_HTTP
    host: str = "0.0.0.0"
    port: int = 8000
    sse_config: Optional[SSEConfig] = None
    http_config: Optional[HTTPConfig] = None
    tls_config: Optional[TLSConfig] = None

    def __post_init__(self):
        """初始化后处理"""
        if self.sse_config is None:
            self.sse_config = SSEConfig()
        if self.http_config is None:
            self.http_config = HTTPConfig()
        if self.tls_config is None:
            self.tls_config = TLSConfig()

    def get_run_kwargs(self) -> Dict[str, Any]:
        """
        获取 FastMCP.run() 所需的参数。

        Returns:
            dict: 传递给 FastMCP.run() 的关键字参数

        Note:
            FastMCP 目前只接受 transport 参数，其他配置需要通过其他方式设置。
        """
        kwargs = {
            "transport": self.transport.value,
        }

        # 为 HTTP/SSE 传输添加额外配置
        if self.transport in [TransportType.SSE, TransportType.STREAMABLE_HTTP]:
            kwargs.update({
                "host": self.host,
                "port": self.port,
            })

            # 添加 HTTP 配置
            if self.http_config:
                kwargs.update({
                    "max_body_size": self.http_config.max_body_size,
                    "request_timeout": self.http_config.request_timeout,
                })

            # 添加 TLS 配置
            if self.tls_config and self.tls_config.enabled:
                kwargs.update({
                    "ssl_certfile": self.tls_config.cert_file,
                    "ssl_keyfile": self.tls_config.key_file,
                })

        return kwargs

    def get_connection_string(self) -> str:
        """
        获取连接字符串

        Returns:
            连接字符串
        """
        if self.transport == TransportType.STDIO:
            return "stdio"

        protocol = "https" if self.tls_config and self.tls_config.enabled else "http"
        return f"{protocol}://{self.host}:{self.port}"

    @classmethod
    def from_settings(cls) -> "TransportConfig":
        """
        从全局配置创建传输配置

        Returns:
            TransportConfig 实例
        """
        return cls(
            transport=settings.mcp.transport,
            host=settings.mcp.host,
            port=settings.mcp.port,
        )

    @classmethod
    def from_string(
        cls,
        transport_str: str,
        host: str = "0.0.0.0",
        port: int = 8000,
        **kwargs,
    ) -> "TransportConfig":
        """
        从字符串创建传输配置

        Args:
            transport_str: 传输类型字符串 (stdio, sse, streamable-http)
            host: HTTP 模式监听地址
            port: HTTP 模式监听端口
            **kwargs: 其他配置参数

        Returns:
            TransportConfig: 传输配置实例

        Raises:
            ValueError: 无效的传输类型
        """
        transport_map = {
            "stdio": TransportType.STDIO,
            "sse": TransportType.SSE,
            "streamable-http": TransportType.STREAMABLE_HTTP,
        }

        if transport_str not in transport_map:
            raise ValueError(
                f"Invalid transport type: {transport_str}. "
                f"Valid options: {list(transport_map.keys())}"
            )

        return cls(
            transport=transport_map[transport_str],
            host=host,
            port=port,
            **kwargs,
        )

    def validate(self) -> bool:
        """
        验证配置

        Returns:
            配置是否有效
        """
        # 检查端口范围
        if not (1 <= self.port <= 65535):
            return False

        # 检查 TLS 配置
        if self.tls_config and self.tls_config.enabled:
            if not self.tls_config.cert_file or not self.tls_config.key_file:
                return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "transport": self.transport.value,
            "host": self.host,
            "port": self.port,
            "sse_config": self.sse_config.dict() if self.sse_config else None,
            "http_config": self.http_config.dict() if self.http_config else None,
            "tls_config": self.tls_config.dict() if self.tls_config else None,
            "connection_string": self.get_connection_string(),
        }


# 预定义的传输配置
TRANSPORT_PRESETS: Dict[str, TransportConfig] = {
    "stdio": TransportConfig(transport=TransportType.STDIO),
    "sse": TransportConfig(transport=TransportType.SSE),
    "http": TransportConfig(transport=TransportType.STREAMABLE_HTTP),
    "https": TransportConfig(
        transport=TransportType.STREAMABLE_HTTP,
        tls_config=TLSConfig(enabled=True),
    ),
}


def get_transport_config(
    transport: Union[str, TransportType],
    host: str = "0.0.0.0",
    port: int = 8000,
    preset: Optional[str] = None,
) -> TransportConfig:
    """
    获取传输配置的便捷函数

    Args:
        transport: 传输类型字符串或枚举
        host: HTTP 模式监听地址
        port: HTTP 模式监听端口
        preset: 预设配置名称

    Returns:
        TransportConfig: 传输配置实例

    Example:
        >>> config = get_transport_config("stdio")
        >>> config.transport
        <TransportType.STDIO: 'stdio'>
    """
    # 使用预设配置
    if preset and preset in TRANSPORT_PRESETS:
        config = TRANSPORT_PRESETS[preset]
        config.host = host
        config.port = port
        return config

    # 从字符串创建
    if isinstance(transport, str):
        return TransportConfig.from_string(transport, host, port)

    # 直接使用枚举
    return TransportConfig(transport=transport, host=host, port=port)