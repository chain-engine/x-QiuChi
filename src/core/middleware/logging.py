"""
日志中间件

记录请求和响应的详细信息，用于调试和监控。
"""

import time
import inspect
from typing import Any, Dict
from dataclasses import asdict

from .base import Middleware, RequestContext, ResponseContext, Handler
from ..logging.logger import get_logger

logger = get_logger(__name__)


class LoggingMiddleware(Middleware):
    """
    日志中间件

    记录请求的详细信息，包括执行时间、结果等。
    """

    def __init__(self, log_request: bool = True, log_response: bool = True):
        """
        初始化日志中间件

        Args:
            log_request: 是否记录请求信息
            log_response: 是否记录响应信息
        """
        self.log_request = log_request
        self.log_response = log_response

    async def handle(
        self,
        request: RequestContext,
        next_handler: Handler,
    ) -> ResponseContext:
        """
        处理请求，记录日志

        Args:
            request: 请求上下文
            next_handler: 下一个处理器

        Returns:
            响应上下文
        """
        # 记录请求开始
        start_time = time.time()
        request_id = request.request.get("id", "unknown")
        method = request.request.get("method", "unknown")

        if self.log_request:
            self._log_request(request, request_id)

        try:
            # 调用下一个处理器
            response = await next_handler(request)

            # 计算执行时间
            execution_time = time.time() - start_time

            if self.log_response:
                self._log_response(response, request_id, execution_time, method)

            return response

        except Exception as e:
            # 计算执行时间（即使出错）
            execution_time = time.time() - start_time

            # 记录错误
            logger.error(
                f"Request {request_id} failed after {execution_time:.3f}s: {e}"
            )
            raise

    def _log_request(self, request: RequestContext, request_id: str) -> None:
        """记录请求信息"""
        request_data = request.request

        # 提取关键信息
        method = request_data.get("method", "unknown")
        params = request_data.get("params", {})

        # 敏感信息过滤（例如密码）
        filtered_params = self._filter_sensitive_data(params)

        # 获取源代码位置信息
        source_location = self._get_source_location(method, request)

        # 构建日志消息
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
        """记录响应信息"""
        response_data = response.response

        # 检查是否是错误响应
        if "error" in response_data:
            error_data = response_data.get("error", {})
            error_code = error_data.get("code", "unknown")
            error_message = error_data.get("message", "")

            log_message = f"Request {request_id} ({method}) failed after {execution_time:.3f}s: "
            log_message += f"code={error_code}, message={error_message}"
            logger.warning(log_message)
        else:
            # 成功响应
            logger.info(
                f"Request {request_id} ({method}) completed in {execution_time:.3f}s"
            )

    def _filter_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        过滤敏感数据

        Args:
            data: 原始数据

        Returns:
            过滤后的数据
        """
        if not isinstance(data, dict):
            return data

        filtered = data.copy()

        # 敏感字段列表
        sensitive_fields = {
            "password", "token", "api_key", "secret", "auth",
            "credentials", "key", "passphrase", "private_key"
        }

        for field in sensitive_fields:
            if field in filtered:
                filtered[field] = "***REDACTED***"

        # 递归处理嵌套字典
        for key, value in filtered.items():
            if isinstance(value, dict):
                filtered[key] = self._filter_sensitive_data(value)
            elif isinstance(value, list):
                filtered[key] = [
                    self._filter_sensitive_data(item) if isinstance(item, dict) else item
                    for item in value
                ]

        return filtered

    def _get_source_location(self, method_name: str, request: RequestContext) -> str:
        """
        获取方法/工具的源代码位置

        Args:
            method_name: 方法/工具名称
            request: 请求上下文

        Returns:
            源代码位置字符串，格式为 "filename:lineno"，如果无法获取则返回 None
        """
        # 尝试从 server 的注册表中查找
        server = None
        if hasattr(request, "server"):
            server = request.server

        if server and hasattr(server, "registry"):
            try:
                from ..plugins.registry import RegistryItemType
                # 查找工具
                item = server.registry.get_item(method_name)
                if item and item.type == RegistryItemType.TOOL:
                    # 获取包装函数的源位置
                    func = item.item
                    return self._get_function_source(func)
            except Exception:
                pass

        # 如果找不到，尝试通过其他方式获取
        return None

    def _get_function_source(self, func: Any) -> str:
        """
        获取函数的源代码位置

        Args:
            func: 函数对象

        Returns:
            源代码位置字符串，格式为 "filename:lineno:column"
        """
        try:
            # 获取原始函数（如果是包装函数）
            original_func = func
            while hasattr(original_func, "__wrapped__"):
                original_func = getattr(original_func, "__wrapped__")

            # 获取源文件和行号
            source_file = inspect.getsourcefile(original_func)
            if not source_file:
                return None

            # 转换为相对路径
            import os
            try:
                # 获取项目根目录
                import pathlib
                project_root = pathlib.Path(__file__).parent.parent.parent.parent.resolve()
                rel_path = os.path.relpath(source_file, str(project_root))
            except Exception:
                rel_path = source_file

            # 获取行号
            _, lineno = inspect.getsourcelines(original_func)

            # 尝试获取列号
            column = None
            try:
                # 使用 findsource 获取更详细的信息
                lines, start_lineno = inspect.findsource(original_func)
                if lines:
                    # 查找函数定义行
                    func_line = lines[start_lineno]  # findsource 返回从 0 开始的行号
                    # 找到 "def " 关键字的位置
                    def_pos = func_line.find("def ")
                    if def_pos != -1:
                        column = def_pos
            except Exception:
                pass

            if column is not None:
                return f"{rel_path}:{lineno}:{column}"
            else:
                return f"{rel_path}:{lineno}"

        except Exception:
            return None

    @staticmethod
    def enable_performance_logging(threshold: float = 1.0):
        """
        启用性能日志记录

        Args:
            threshold: 性能阈值（秒），超过此值的请求会被记录为警告

        Returns:
            配置好的日志中间件实例
        """
        middleware = LoggingMiddleware()

        # 保存原始日志方法
        original_log_response = middleware._log_response

        def enhanced_log_response(response, request_id, execution_time, method="unknown"):
            # 调用原始方法
            original_log_response(response, request_id, execution_time, method)

            # 检查是否超过阈值
            if execution_time > threshold:
                logger.warning(
                    f"Performance warning: Request {request_id} ({method}) took {execution_time:.3f}s "
                    f"(threshold: {threshold}s)"
                )

        # 替换方法
        middleware._log_response = enhanced_log_response

        return middleware