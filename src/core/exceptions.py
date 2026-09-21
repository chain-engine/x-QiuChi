#!/usr/bin/env python3
"""
统一异常处理模块

本模块定义了应用程序的异常层级结构和全局异常处理器。
所有自定义异常继承自 AppException，分为业务异常（4xx）和系统异常（5xx）两类。

异常层级：
    AppException                          # 应用异常基类
    ├── BusinessException                 # 业务异常 (4xx)
    │   ├── ValidationException           # 参数校验异常 (422)
    │   ├── AuthenticationException       # 认证异常 (401)
    │   ├── AuthorizationException        # 授权异常 (403)
    │   └── NotFoundException             # 资源未找到 (404)
    └── SystemException                   # 系统异常 (5xx)
        ├── DatabaseException             # 数据库异常 (500)
        └── ExternalServiceException      # 外部服务异常 (502)

Usage:
    from src.core.exceptions import BusinessException, register_exception_handlers

    # 在业务代码中抛出异常
    raise BusinessException("Order not found")

    # 在 FastAPI 应用中注册全局处理器
    register_exception_handlers(app)
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.api.response import error_response
from src.constants import MSG_INTERNAL_ERROR, MSG_VALIDATION_ERROR


class AppException(Exception):
    """应用异常基类。

    所有自定义异常必须继承此类，禁止直接使用 Python 内置异常。

    Attributes:
        message: 异常描述信息
        code: HTTP 状态码
        details: 附加详情信息
    """

    def __init__(
        self,
        message: str = "Application error",
        code: int = 500,
        details: Any | None = None,
    ) -> None:
        """初始化应用异常。

        Args:
            message: 异常描述信息
            code: HTTP 状态码
            details: 附加详情（如校验错误列表）
        """
        self.message: str = message
        self.code: int = code
        self.details: Any | None = details
        super().__init__(self.message)


class BusinessException(AppException):
    """业务异常基类（4xx 错误）。

    用于表示由客户端请求引起的可预期错误，如参数校验失败、资源不存在等。
    """

    def __init__(
        self,
        message: str = "Business error",
        code: int = 400,
        details: Any | None = None,
    ) -> None:
        """初始化业务异常。

        Args:
            message: 异常描述信息
            code: HTTP 状态码（默认 400）
            details: 附加详情
        """
        super().__init__(message=message, code=code, details=details)


class ValidationException(BusinessException):
    """参数校验异常。

    用于请求参数不符合校验规则时抛出。
    """

    def __init__(
        self,
        message: str = "Validation error",
        details: Any | None = None,
    ) -> None:
        """初始化校验异常。

        Args:
            message: 异常描述信息
            details: 校验错误详情列表
        """
        super().__init__(message=message, code=422, details=details)


class AuthenticationException(BusinessException):
    """认证异常。

    用于身份认证失败时抛出（如 token 无效或过期）。
    """

    def __init__(
        self,
        message: str = "Authentication failed",
        details: Any | None = None,
    ) -> None:
        """初始化认证异常。

        Args:
            message: 异常描述信息
            details: 附加详情
        """
        super().__init__(message=message, code=401, details=details)


class AuthorizationException(BusinessException):
    """授权异常。

    用于权限不足时抛出（如用户无权访问某资源）。
    """

    def __init__(
        self,
        message: str = "Permission denied",
        details: Any | None = None,
    ) -> None:
        """初始化授权异常。

        Args:
            message: 异常描述信息
            details: 附加详情
        """
        super().__init__(message=message, code=403, details=details)


class NotFoundException(BusinessException):
    """资源未找到异常。

    用于请求的资源不存在时抛出。
    """

    def __init__(
        self,
        message: str = "Resource not found",
        details: Any | None = None,
    ) -> None:
        """初始化资源未找到异常。

        Args:
            message: 异常描述信息
            details: 附加详情
        """
        super().__init__(message=message, code=404, details=details)


class ConflictException(BusinessException):
    """资源冲突异常（409）。

    用于资源已存在、唯一约束冲突、版本号冲突等场景。
    """

    def __init__(
        self,
        message: str = "Resource conflict",
        details: Any | None = None,
    ) -> None:
        """初始化资源冲突异常。

        Args:
            message: 异常描述信息
            details: 附加详情
        """
        super().__init__(message=message, code=409, details=details)


class SystemException(AppException):
    """系统异常基类（5xx 错误）。

    用于表示由服务端内部错误引起的不可预期异常。
    """

    def __init__(
        self,
        message: str = "Internal server error",
        code: int = 500,
        details: Any | None = None,
    ) -> None:
        """初始化系统异常。

        Args:
            message: 异常描述信息
            code: HTTP 状态码（默认 500）
            details: 附加详情
        """
        super().__init__(message=message, code=code, details=details)


class DatabaseException(SystemException):
    """数据库异常。

    用于数据库操作失败时抛出。
    """

    def __init__(
        self,
        message: str = "Database error",
        details: Any | None = None,
    ) -> None:
        """初始化数据库异常。

        Args:
            message: 异常描述信息
            details: 附加详情
        """
        super().__init__(message=message, code=500, details=details)


class ExternalServiceException(SystemException):
    """外部服务异常。

    用于调用外部服务（如第三方 API、消息队列）失败时抛出。
    """

    def __init__(
        self,
        message: str = "External service error",
        details: Any | None = None,
    ) -> None:
        """初始化外部服务异常。

        Args:
            message: 异常描述信息
            details: 附加详情
        """
        super().__init__(message=message, code=502, details=details)


async def _app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """处理所有 AppException 及其子类的全局异常处理器。

    生产环境下，5xx 异常的 details 不会暴露给客户端，避免泄漏内部栈信息；
    仅在 DEBUG/开发环境下透出。

    Args:
        request: 当前请求对象
        exc: 捕获的应用异常

    Returns:
        JSONResponse: 标准化的错误响应
    """
    from src.core.config import settings
    from src.core.logger import logger

    request_id: str | None = getattr(request.state, "request_id", None)
    log_level: str = "ERROR" if exc.code >= 500 else "WARNING"
    logger.bind(request_id=request_id or "-").log(
        log_level,
        f"{type(exc).__name__}: {exc.message}",
    )

    # 仅在非生产环境或 4xx 业务异常时透出 details
    show_details = exc.code < 500 or settings.is_development
    data: dict[str, Any] | None = None
    if exc.details is not None and show_details:
        data = {"details": exc.details}

    return error_response(
        request=request,
        code=exc.code,
        message=exc.message,
        data=data,
    )


async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """处理 Pydantic 请求校验异常。

    Args:
        request: 当前请求对象
        exc: FastAPI 校验异常

    Returns:
        JSONResponse: 包含校验错误详情的标准化错误响应
    """
    from src.core.logger import logger

    request_id: str | None = getattr(request.state, "request_id", None)
    errors: list[dict[str, Any]] = exc.errors()

    logger.bind(request_id=request_id or "-").warning(
        f"Validation error: {errors}"
    )

    return error_response(
        request=request,
        code=422,
        message=MSG_VALIDATION_ERROR,
        data={"details": errors},
    )


async def _generic_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """处理所有未捕获的异常的兜底处理器。

    Args:
        request: 当前请求对象
        exc: 捕获的异常

    Returns:
        JSONResponse: 标准化的 500 错误响应
    """
    from src.core.logger import logger

    request_id: str | None = getattr(request.state, "request_id", None)
    logger.bind(request_id=request_id or "-").exception(
        f"Unhandled exception: {exc}"
    )

    return error_response(
        request=request,
        code=500,
        message=MSG_INTERNAL_ERROR,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器到 FastAPI 应用。

    包括 AppException 层级、Pydantic 校验异常、以及通用异常兜底处理。
    必须在 create_app() 中调用。

    Args:
        app: FastAPI 应用实例
    """
    app.add_exception_handler(AppException, _app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _generic_exception_handler)  # type: ignore[arg-type]


__all__ = [
    "AppException",
    "BusinessException",
    "SystemException",
    "ValidationException",
    "AuthenticationException",
    "AuthorizationException",
    "NotFoundException",
    "ConflictException",
    "DatabaseException",
    "ExternalServiceException",
    "register_exception_handlers",
]
