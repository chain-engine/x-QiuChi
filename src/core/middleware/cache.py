"""
缓存中间件

提供请求缓存功能，提高重复请求的响应速度。
"""

from __future__ import annotations

import hashlib
import json
import asyncio
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
    """内存缓存后端（异步安全）"""

    def __init__(self, max_size: int = 1024):
        self._cache: Dict[str, Tuple[Any, Optional[float]]] = {}
        self._lock = asyncio.Lock()
        self._max_size = max_size

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            value, expire_time = entry
            if expire_time is not None and time.time() > expire_time:
                self._cache.pop(key, None)
                return None
            return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        async with self._lock:
            # 容量上限保护：避免无界增长
            if key not in self._cache and len(self._cache) >= self._max_size:
                # 简单驱逐：删除最早过期的；否则删除任意一个
                victim = None
                for k, (_, exp) in self._cache.items():
                    if exp is None or time.time() > exp:
                        victim = k
                        break
                if victim is None:
                    victim = next(iter(self._cache))
                self._cache.pop(victim, None)
            expire_time = time.time() + ttl if ttl else None
            self._cache[key] = (value, expire_time)
            return True

    async def delete(self, key: str) -> bool:
        async with self._lock:
            return self._cache.pop(key, None) is not None

    async def clear(self) -> bool:
        async with self._lock:
            self._cache.clear()
            return True

    async def get_stats(self) -> Dict[str, Any]:
        async with self._lock:
            total = len(self._cache)
            now = time.time()
            expired = sum(
                1 for _, (_, exp) in self._cache.items()
                if exp is not None and now > exp
            )
            return {
                "backend": "MemoryCacheBackend",
                "total_entries": total,
                "expired_entries": expired,
                "valid_entries": total - expired,
                "max_size": self._max_size,
            }


class CacheMiddleware(Middleware):
    """
    缓存中间件

    缓存请求的响应结果，减少重复计算和外部调用。
    """

    def __init__(
        self,
        cache_backend: Optional[CacheBackend] = None,
        default_ttl: int = 300,
        enabled: bool = True,
        cacheable_methods: Optional[list] = None,
        bypass_header: str = "X-Cache-Bypass",
    ):
        self.cache_backend = cache_backend or MemoryCacheBackend()
        self.default_ttl = default_ttl
        self.enabled = enabled
        self.cacheable_methods = set(cacheable_methods or [])
        self.bypass_header = bypass_header

        logger.debug(
            f"CacheMiddleware initialized (enabled={enabled}, default_ttl={default_ttl}s)"
        )

    async def handle(
        self,
        request: RequestContext,
        next_handler: Handler,
    ) -> ResponseContext:
        if not self.enabled:
            return await next_handler(request)

        if self._should_bypass_cache(request):
            logger.debug(f"Bypassing cache for request: {request.request.get('id', 'unknown')}")
            return await next_handler(request)

        method = request.request.get("method", "")
        if self.cacheable_methods and method not in self.cacheable_methods:
            return await next_handler(request)

        cache_key = self._generate_cache_key(request)

        cached_response = await self.cache_backend.get(cache_key)
        if cached_response is not None:
            logger.debug(f"Cache hit for key: {cache_key[:32]}...")
            request.metadata["cache_hit"] = True
            return ResponseContext(response=cached_response)

        logger.debug(f"Cache miss for key: {cache_key[:32]}...")
        response = await next_handler(request)

        if self._should_cache_response(response):
            ttl = self._get_ttl_for_request(request)
            await self.cache_backend.set(cache_key, response.response, ttl)
            logger.debug(f"Cached response for key: {cache_key[:32]}... (ttl={ttl}s)")

        return response

    def _should_bypass_cache(self, request: RequestContext) -> bool:
        headers = request.request.get("headers", {})
        # 也支持从一级 metadata 读取（适配 FastMCP HTTP 头注入场景）
        meta_headers = request.metadata.get("headers", {}) if hasattr(request, "metadata") else {}
        bypass = (
            headers.get(self.bypass_header, "")
            or meta_headers.get(self.bypass_header, "")
        )
        return str(bypass).lower() in ("true", "1", "yes")

    def _generate_cache_key(self, request: RequestContext) -> str:
        request_data = request.request
        method = request_data.get("method", "")
        params = request_data.get("params", {})
        headers = request_data.get("headers", {})

        cache_dict = {
            "method": method,
            "params": self._normalize_params(params),
        }

        # 使用 SHA-256 做摘要（避免 MD5 在 FIPS 环境报错）
        auth_header = headers.get("Authorization")
        if auth_header:
            cache_dict["auth_hash"] = hashlib.sha256(auth_header.encode()).hexdigest()

        cache_str = json.dumps(cache_dict, sort_keys=True, default=str)
        return f"qiuchi:cache:{hashlib.sha256(cache_str.encode()).hexdigest()}"

    def _normalize_params(self, params: Any) -> Any:
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
        return "error" not in response.response

    def _get_ttl_for_request(self, request: RequestContext) -> int:
        headers = request.request.get("headers", {})
        params = request.request.get("params", {})
        meta_headers = request.metadata.get("headers", {}) if hasattr(request, "metadata") else {}

        ttl = (
            headers.get("X-Cache-TTL")
            or meta_headers.get("X-Cache-TTL")
            or params.get("cache_ttl")
            or self.default_ttl
        )
        try:
            return int(ttl)
        except (ValueError, TypeError):
            return self.default_ttl

    async def clear_cache(self) -> bool:
        logger.info("Clearing cache...")
        return await self.cache_backend.clear()

    async def invalidate_method(self, method: str) -> int:
        logger.warning(f"Memory cache does not support pattern invalidation for method: {method}")
        return 0

    async def get_stats(self) -> Dict[str, Any]:
        return await self.cache_backend.get_stats()
