"""
错误处理中间件

统一处理请求执行过程中的异常，提供友好的错误响应。
"""

from __future__ import annotations

import traceback
from typing import Any, Dict, Optional

from .base import Middleware, RequestContext, ResponseContext, Handler
from core.logging.logger import get_logger

logger = get_logger(__name__)

# JSON-RPC 2.0 标准错误码
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
# 自定义错误码（-32000 ~ -32099）
AUTH_ERROR = -32001
PERMISSION_ERROR = -32002
RATE_LIMIT_ERROR = -32003


class ErrorHandlerMiddleware(Middleware):
    """错误处理中间件（最外层）"""

    def __init__(self, include_traceback: bool = False):
        self.include_traceback = include_traceback

    async def handle(
        self,
        request: RequestContext,
        next_handler: Handler,
    ) -> ResponseContext:
        try:
            return await next_handler(request)
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            if self.include_traceback:
                logger.error(traceback.format_exc())
            error_response = self._build_error_response(e, request)
            return ResponseContext(response=error_response)

    def _build_error_response(
        self,
        error: Exception,
        request: RequestContext,
    ) -> Dict[str, Any]:
        error_type = type(error).__name__
        error_message = str(error)

        error_response: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "error": {
                "code": INTERNAL_ERROR,
                "message": f"Internal error: {error_type}",
                "data": {
                    "type": error_type,
                    "message": error_message,
                    "request_id": request.request.get("id"),
                },
            },
        }

        # JSON-RPC 规范要求响应带 id（即便发生错误）
        rid = request.request.get("id")
        if rid is not None:
            error_response["id"] = rid

        if self.include_traceback:
            error_response["error"]["data"]["traceback"] = traceback.format_exc()

        return error_response

    @staticmethod
    def create_validation_error(message: str, data: Optional[Dict[str, Any]] = None, rid: Any = None) -> Dict[str, Any]:
        resp = {
            "jsonrpc": "2.0",
            "error": {
                "code": INVALID_PARAMS,
                "message": f"Invalid params: {message}",
                "data": data or {},
            },
        }
        if rid is not None:
            resp["id"] = rid
        return resp

    @staticmethod
    def create_method_not_found_error(method: str, rid: Any = None) -> Dict[str, Any]:
        resp = {
            "jsonrpc": "2.0",
            "error": {
                "code": METHOD_NOT_FOUND,
                "message": f"Method not found: {method}",
                "data": {"method": method},
            },
        }
        if rid is not None:
            resp["id"] = rid
        return resp


__all__ = [
    "ErrorHandlerMiddleware",
    "PARSE_ERROR",
    "INVALID_REQUEST",
    "METHOD_NOT_FOUND",
    "INVALID_PARAMS",
    "INTERNAL_ERROR",
    "AUTH_ERROR",
    "PERMISSION_ERROR",
    "RATE_LIMIT_ERROR",
]
