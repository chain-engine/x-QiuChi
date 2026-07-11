"""
QiuChi 核心配置类

基于 Pydantic Settings 的配置管理系统，支持：
- 多配置源（环境变量 > YAML 文件 > 默认值）
- 自动类型转换和验证
- 热重载支持
- 嵌套配置模型
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union
from enum import Enum

from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[4]


# 从共享类型模块导入
from core.types import TransportType, LogLevel, LogOutput


class MCPConfig(BaseSettings):
    """MCP 服务器配置"""

    server_name: str = Field(default="QiuChi", description="服务器名称")
    version: str = Field(default="1.0.0", description="服务器版本")
    transport: TransportType = Field(default=TransportType.STREAMABLE_HTTP, description="传输类型")
    host: str = Field(default="0.0.0.0", description="HTTP 监听地址")
    port: int = Field(default=8000, description="HTTP 监听端口", ge=1, le=65535)
    json_response: bool = Field(default=True, description="是否使用 JSON 响应格式")

    model_config = SettingsConfigDict(
        env_prefix="MCP_",
        case_sensitive=False,
    )


class LoggingConfig(BaseSettings):
    """日志配置"""

    level: LogLevel = Field(default=LogLevel.INFO, description="日志级别")
    output: LogOutput = Field(default=LogOutput.BOTH, description="输出目标")
    file_path: str = Field(default="logs/qiuchi.log", description="日志文件路径")
    rotation: str = Field(default="1 day", description="日志轮转周期")
    retention: str = Field(default="7 days", description="日志保留时间")
    format: str = Field(
        default="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{file.name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        description="日志格式"
    )

    model_config = SettingsConfigDict(
        env_prefix="MCP_LOG_",
        case_sensitive=False,
    )

    @validator("file_path")
    def resolve_file_path(cls, v: str) -> str:
        """解析相对路径为绝对路径"""
        path = Path(v)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return str(path)


class FeaturesConfig(BaseSettings):
    """功能开关配置"""

    tools: bool = Field(default=True, description="是否启用 Tools 原语")
    resources: bool = Field(default=True, description="是否启用 Resources 原语")
    prompts: bool = Field(default=True, description="是否启用 Prompts 原语")
    middleware: bool = Field(default=True, description="是否启用中间件")
    cache: bool = Field(default=False, description="是否启用缓存")

    model_config = SettingsConfigDict(
        env_prefix="MCP_FEATURES_",
        case_sensitive=False,
    )


class PluginConfig(BaseSettings):
    """插件配置"""

    auto_discovery: bool = Field(default=True, description="是否自动发现插件")
    discovery_paths: List[str] = Field(
        default_factory=lambda: ["src.plugins", "src.examples"],
        description="插件发现路径"
    )
    enabled_plugins: List[str] = Field(
        default_factory=list,
        description="启用的插件列表（空列表表示启用所有）"
    )
    disabled_plugins: List[str] = Field(
        default_factory=list,
        description="禁用的插件列表"
    )

    model_config = SettingsConfigDict(
        env_prefix="MCP_PLUGIN_",
        case_sensitive=False,
    )


class AuthConfig(BaseSettings):
    """认证配置"""

    enabled: bool = Field(default=False, description="是否启用认证")
    required: bool = Field(default=True, description="是否必须认证")
    exempt_methods: List[str] = Field(default_factory=list, description="免认证的方法列表")

    model_config = SettingsConfigDict(
        env_prefix="MCP_AUTH_",
        case_sensitive=False,
    )


class MiddlewareConfig(BaseSettings):
    """中间件配置"""

    auth: AuthConfig = Field(default_factory=AuthConfig)

    model_config = SettingsConfigDict(
        env_prefix="MCP_MIDDLEWARE_",
        case_sensitive=False,
    )


class Settings(BaseSettings):
    """
    全局配置类（单例模式）

    支持从多个源加载配置：
    1. 环境变量（最高优先级）
    2. YAML 配置文件
    3. 默认值（最低优先级）
    """

    # 配置模型
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)
    plugins: PluginConfig = Field(default_factory=PluginConfig)
    middleware: MiddlewareConfig = Field(default_factory=MiddlewareConfig)

    # 配置文件路径
    config_file: Optional[str] = Field(default="config.yaml", description="配置文件路径")

    model_config = SettingsConfigDict(
        env_prefix="QIUCHI_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def __init__(self, **kwargs: Any) -> None:
        """初始化配置，加载 YAML 文件"""
        super().__init__(**kwargs)
        self._load_yaml_config()

    def _load_yaml_config(self) -> None:
        """从 YAML 配置文件加载配置"""
        if not self.config_file:
            return

        config_path = Path(self.config_file)
        if not config_path.is_absolute():
            config_path = PROJECT_ROOT / config_path

        if not config_path.exists():
            return

        try:
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                yaml_config = yaml.safe_load(f) or {}

            # 更新配置（Pydantic 会自动合并）
            if yaml_config:
                self._update_from_dict(yaml_config)
        except ImportError:
            pass  # YAML 不可用，跳过
        except Exception as e:
            print(f"Warning: Failed to load YAML config: {e}", file=__import__("sys").stderr)

    def _update_from_dict(self, config_dict: Dict[str, Any]) -> None:
        """从字典更新配置"""
        # 手动更新嵌套配置
        for key, value in config_dict.items():
            if hasattr(self, key):
                current_value = getattr(self, key)
                if isinstance(current_value, BaseSettings) and isinstance(value, dict):
                    # 递归更新嵌套配置
                    current_value_dict = current_value.model_dump()
                    current_value_dict.update(value)
                    setattr(self, key, type(current_value)(**current_value_dict))
                else:
                    setattr(self, key, value)

    def reload(self) -> None:
        """重新加载配置（热重载）"""
        # 清除缓存的环境变量
        os.environ.pop(f"QIUCHI_CONFIG_FILE", None)

        # 重新加载配置
        new_settings = Settings()
        self.__dict__.update(new_settings.__dict__)

    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典"""
        return self.model_dump()

    def save_to_yaml(self, file_path: Optional[str] = None) -> bool:
        """保存配置到 YAML 文件"""
        try:
            import yaml
            save_path = Path(file_path) if file_path else Path(self.config_file or "config.yaml")
            if not save_path.is_absolute():
                save_path = PROJECT_ROOT / save_path

            save_path.parent.mkdir(parents=True, exist_ok=True)

            with open(save_path, "w", encoding="utf-8") as f:
                yaml.dump(self.to_dict(), f, default_flow_style=False, allow_unicode=True)

            return True
        except Exception:
            return False


# 全局配置实例（单例）
settings: Settings = Settings()