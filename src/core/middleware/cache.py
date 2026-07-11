"""
缓存中间件

提供请求缓存功能，提高重复请求的响应速度。
"""

import hashlib
import json
import time
from typing import Any, Dict, Optional, Tuple
from abc import ABC, abstractmethod

from .base import Middleware, RequestContext, ResponseContext, Handler
from core.logging.logger import get_logger

logger = get_logger(__name__)


class CacheBackend(ABC):
    """缓存后端基类"""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """删除缓存值"""
        pass

    @abstractmethod
    async def clear(self) -> bool:
        """清空缓存"""
        pass

    async def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息（默认实现）"""
        return {"backend": type(self).__name__}


class MemoryCacheBackend(CacheBackend):
    """内存缓存后端"""

    def __init__(self):
        self._cache: Dict[str, Tuple[Any, Optional[float]]] = {}

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if key not in self._cache:
            return None

        value, expire_time = self._cache[key]

        # 检查是否过期
        if expire_time and time.time() > expire_time:
            del self._cache[key]
            return None

        return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        expire_time = time.time() + ttl if ttl else None
        self._cache[key] = (value, expire_time)
        return True

    async def delete(self, key: str) -> bool:
        """删除缓存值"""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    async def clear(self) -> bool:
        """清空缓存"""
        self._cache.clear()
        return True

    async def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total = len(self._cache)
        expired = sum(
            1 for expire_time in self._cache.values()
            if expire_time[1] and time.time() > expire_time[1]
        )
        return {
            "total_entries": total,
            "expired_entries": expired,
            "valid_entries": total - expired,
        }


class CacheMiddleware(Middleware):
    """
    缓存中间件

    缓存请求的响应结果，减少重复计算和外部调用。
    """

    def __init__(
        self,
        cache_backend: Optional[CacheBackend] = None,
        default_ttl: int = 300,  # 默认5分钟
        enabled: bool = True,
        cacheable_methods: Optional[list[str]] = None,
        bypass_header: str = "X-Cache-Bypass",
    ):
        """
        初始化缓存中间件

        Args:
            cache_backend: 缓存后端（默认使用内存缓存）
            default_ttl: 默认缓存时间（秒）
            enabled: 是否启用缓存
            cacheable_methods: 可缓存的方法列表（None 表示所有方法）
            bypass_header: 绕过缓存的请求头
        """
        self.cache_backend = cache_backend or MemoryCacheBackend()
        self.default_ttl = default_ttl
        self.enabled = enabled
        self.cacheable_methods = set(cacheable_methods or [])
        self.bypass_header = bypass_header

        logger.debug(
            f"CacheMiddleware initialized (enabled={enabled}, "
            f"default_ttl={default_ttl}s)"
        )

    async def handle(
        self,
        request: RequestContext,
        next_handler: Handler,
    ) -> ResponseContext:
        """
        处理缓存

        Args:
            request: 请求上下文
            next_handler: 下一个处理器

        Returns:
            响应上下文
        """
        # 检查缓存是否启用
        if not self.enabled:
            return await next_handler(request)

        # 检查是否应该绕过缓存
        if self._should_bypass_cache(request):
            logger.debug(f"Bypassing cache for request: {request.request.get('id', 'unknown')}")
            return await next_handler(request)

        # 检查方法是否可缓存
        method = request.request.get("method", "")
        if self.cacheable_methods and method not in self.cacheable_methods:
            return await next_handler(request)

        # 生成缓存键
        cache_key = self._generate_cache_key(request)

        # 尝试从缓存获取
        cached_response = await self.cache_backend.get(cache_key)
        if cached_response is not None:
            logger.debug(f"Cache hit for key: {cache_key[:32]}...")
            request.metadata["cache_hit"] = True
            return ResponseContext(response=cached_response)

        # 缓存未命中，执行请求
        logger.debug(f"Cache miss for key: {cache_key[:32]}...")
        response = await next_handler(request)

        # 缓存响应（仅缓存成功响应）
        if self._should_cache_response(response):
            ttl = self._get_ttl_for_request(request)
            await self.cache_backend.set(cache_key, response.response, ttl)
            logger.debug(f"Cached response for key: {cache_key[:32]}... (ttl={ttl}s)")

        return response

    def _should_bypass_cache(self, request: RequestContext) -> bool:
        """检查是否应该绕过缓存"""
        headers = request.request.get("headers", {})
        return headers.get(self.bypass_header, "").lower() in ["true", "1", "yes"]

    def _generate_cache_key(self, request: RequestContext) -> str:
        """生成缓存键"""
        request_data = request.request

        # 提取关键信息
        method = request_data.get("method", "")
        params = request_data.get("params", {})
        headers = request_data.get("headers", {})

        # 创建可哈希的字典（排除某些可能变化的字段）
        cache_dict = {
            "method": method,
            "params": self._normalize_params(params),
            # 可以添加其他影响缓存的字段
        }

        # 添加特定头信息（如认证信息）
        auth_header = headers.get("Authorization")
        if auth_header:
            cache_dict["auth_hash"] = hashlib.md5(auth_header.encode()).hexdigest()

        # 序列化并哈希
        cache_str = json.dumps(cache_dict, sort_keys=True)
        return f"qiuchi:cache:{hashlib.sha256(cache_str.encode()).hexdigest()}"

    def _normalize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """规范化参数，使其可哈希"""
        if not isinstance(params, dict):
            return params

        normalized = {}
        for key, value in params.items():
            if isinstance(value, dict):
                normalized[key] = self._normalize_params(value)
            elif isinstance(value, list):
                normalized[key] = [
                    self._normalize_params(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                normalized[key] = value

        return normalized

    def _should_cache_response(self, response: ResponseContext) -> bool:
        """检查是否应该缓存响应"""
        response_data = response.response

        # 不缓存错误响应
        if "error" in response_data:
            return False

        # 可以添加其他条件
        return True

    def _get_ttl_for_request(self, request: RequestContext) -> int:
        """获取请求的缓存时间"""
        # 可以从请求头或参数中获取自定义TTL
        headers = request.request.get("headers", {})
        params = request.request.get("params", {})

        ttl = (
            headers.get("X-Cache-TTL") or
            params.get("cache_ttl") or
            self.default_ttl
        )

        try:
            return int(ttl)
        except (ValueError, TypeError):
            return self.default_ttl

    async def clear_cache(self) -> bool:
        """清空缓存"""
        logger.info("Clearing cache...")
        return await self.cache_backend.clear()

    async def invalidate_method(self, method: str) -> int:
        """
        使特定方法的所有缓存失效

        Args:
            method: 方法名

        Returns:
            失效的缓存数量
        """
        # 注意：内存缓存实现不支持模式匹配
        # 在生产环境中应该使用支持模式匹配的缓存后端（如Redis）
        logger.warning(f"Memory cache does not support pattern invalidation for method: {method}")
        return 0

    async def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return await self.cache_backend.get_stats()