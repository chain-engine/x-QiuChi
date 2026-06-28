"""
错误处理中间件

统一处理请求执行过程中的异常，提供友好的错误响应。
"""

import traceback
from typing import Any, Dict

from .base import Middleware, RequestContext, ResponseContext, Handler
from ..logging.logger import get_logger

logger = get_logger(__name__)


class ErrorHandlerMiddleware(Middleware):
    """
    错误处理中间件

    捕获并处理请求处理过程中的异常，记录日志并返回标准化的错误响应。
    """

    def __init__(self, include_traceback: bool = False):
        """
        初始化错误处理中间件

        Args:
            include_traceback: 是否在错误响应中包含堆栈跟踪（仅开发环境）
        """
        self.include_traceback = include_traceback

    async def handle(
        self,
        request: RequestContext,
        next_handler: Handler,
    ) -> ResponseContext:
        """
        处理请求，捕获异常

        Args:
            request: 请求上下文
            next_handler: 下一个处理器

        Returns:
            响应上下文
        """
        try:
            return await next_handler(request)
        except Exception as e:
            # 记录错误日志
            logger.error(f"Error processing request: {e}")
            if self.include_traceback:
                logger.error(traceback.format_exc())

            # 构建错误响应
            error_response = self._build_error_response(e, request)

            return ResponseContext(response=error_response)

    def _build_error_response(
        self,
        error: Exception,
        request: RequestContext,
    ) -> Dict[str, Any]:
        """
        构建错误响应

        Args:
            error: 异常对象
            request: 请求上下文

        Returns:
            错误响应字典
        """
        error_type = type(error).__name__
        error_message = str(error)

        # 基础错误响应
        error_response = {
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,  # JSON-RPC 内部错误代码
                "message": f"Internal error: {error_type}",
                "data": {
                    "type": error_type,
                    "message": error_message,
                    "request_id": request.request.get("id"),
                }
            }
        }

        # 添加堆栈跟踪（如果启用）
        if self.include_traceback:
            error_response["error"]["data"]["traceback"] = traceback.format_exc()

        return error_response

    @staticmethod
    def create_validation_error(message: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        创建验证错误响应

        Args:
            message: 错误消息
            data: 额外数据

        Returns:
            验证错误响应
        """
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32602,  # JSON-RPC 无效参数代码
                "message": f"Invalid params: {message}",
                "data": data or {},
            }
        }

    @staticmethod
    def create_method_not_found_error(method: str) -> Dict[str, Any]:
        """
        创建方法未找到错误响应

        Args:
            method: 请求的方法名

        Returns:
            方法未找到错误响应
        """
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32601,  # JSON-RPC 方法未找到代码
                "message": f"Method not found: {method}",
                "data": {"method": method},
            }
        }