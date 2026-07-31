"""
日志中间件

记录请求和响应的详细信息，用于调试和监控。
"""

from __future__ import annotations

import time
import inspect
from typing import Any, Dict, Optional

from .base import Middleware, RequestContext, ResponseContext, Handler
from core.logging.logger import get_logger

logger = get_logger(__name__)


class LoggingMiddleware(Middleware):
    """日志中间件"""

    def __init__(
        self,
        log_request: bool = True,
        log_response: bool = True,
        slow_threshold: Optional[float] = None,
    ):
        self.log_request = log_request
        self.log_response = log_response
        self.slow_threshold = slow_threshold

    async def handle(
        self,
        request: RequestContext,
        next_handler: Handler,
    ) -> ResponseContext:
        start_time = time.time()
        request_id = request.request.get("id", "unknown")
        method = request.request.get("method", "unknown")

        if self.log_request:
            self._log_request(request, request_id)

        try:
            response = await next_handler(request)
            execution_time = time.time() - start_time
            if self.log_response:
                self._log_response(response, request_id, execution_time, method)
            if self.slow_threshold is not None and execution_time > self.slow_threshold:
                logger.warning(
                    f"Performance warning: Request {request_id} ({method}) took {execution_time:.3f}s "
                    f"(threshold: {self.slow_threshold}s)"
                )
            return response
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Request {request_id} failed after {execution_time:.3f}s: {e}"
            )
            raise

    def _log_request(self, request: RequestContext, request_id: str) -> None:
        request_data = request.request
        method = request_data.get("method", "unknown")
        params = request_data.get("params", {})
        filtered_params = self._filter_sensitive_data(params)
        source_location = self._get_source_location(method, request)

        log_message = f"Request {request_id}: method={method}"
        if source_location:
            log_message += f", location={source_location}"
        log_message += f", params={filtered_params}"
        logger.info(log_message)

    def _log_response(
        self,
        response: ResponseContext,
        request_id: str,
        execution_time: float,
        method: str,
    ) -> None:
        response_data = response.response
        if "error" in response_data:
            error_data = response_data.get("error", {})
            error_code = error_data.get("code", "unknown")
            error_message = error_data.get("message", "")
            logger.warning(
                f"Request {request_id} ({method}) failed after {execution_time:.3f}s: "
                f"code={error_code}, message={error_message}"
            )
        else:
            logger.info(
                f"Request {request_id} ({method}) completed in {execution_time:.3f}s"
            )

    def _filter_sensitive_data(self, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        filtered = data.copy()
        sensitive_fields = {
            "password", "token", "api_key", "secret", "auth",
            "credentials", "key", "passphrase", "private_key",
        }
        for field in sensitive_fields:
            if field in filtered:
                filtered[field] = "***REDACTED***"
        for key, value in filtered.items():
            if isinstance(value, dict):
                filtered[key] = self._filter_sensitive_data(value)
            elif isinstance(value, list):
                filtered[key] = [
                    self._filter_sensitive_data(item) if isinstance(item, dict) else item
                    for item in value
                ]
        return filtered

    def _get_source_location(self, method_name: str, request: RequestContext) -> Optional[str]:
        server = getattr(request, "server", None)
        if not server or not hasattr(server, "registry"):
            return None
        try:
            from plugins.registry import RegistryItemType
            item = server.registry.get_item(method_name)
            if item and item.type == RegistryItemType.TOOL:
                return self._get_function_source(item.item)
        except Exception:
            return None
        return None

    def _get_function_source(self, func: Any) -> Optional[str]:
        try:
            original = func
            while hasattr(original, "__wrapped__"):
                original = getattr(original, "__wrapped__")
            source_file = inspect.getsourcefile(original)
            if not source_file:
                return None
            import os, pathlib
            try:
                project_root = pathlib.Path(__file__).parent.parent.parent.parent.resolve()
                rel_path = os.path.relpath(source_file, str(project_root))
            except Exception:
                rel_path = source_file
            _, lineno = inspect.getsourcelines(original)
            column = None
            try:
                lines, start_lineno = inspect.findsource(original)
                if lines:
                    func_line = lines[start_lineno]
                    def_pos = func_line.find("def ")
                    if def_pos != -1:
                        column = def_pos
            except Exception:
                pass
            if column is not None:
                return f"{rel_path}:{lineno}:{column}"
            return f"{rel_path}:{lineno}"
        except Exception:
            return None


def enable_performance_logging(threshold: float = 1.0) -> LoggingMiddleware:
    return LoggingMiddleware(slow_threshold=threshold)


__all__ = ["LoggingMiddleware", "enable_performance_logging"]
