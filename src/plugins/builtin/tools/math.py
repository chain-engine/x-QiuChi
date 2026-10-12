"""
数学工具示例

展示如何使用 QiuChi 的装饰器 API 创建工具。
"""

from src.plugins import tool_decorator


@tool_decorator(category="math", subcategory="basic", tags=["arithmetic", "calculation"])
def add(a: float, b: float) -> float:
    """
    两数相加

    Args:
        a: 第一个数字
        b: 第二个数字

    Returns:
        两数之和
    """
    return a + b


@tool_decorator(category="math", subcategory="basic", tags=["arithmetic", "calculation"])
def subtract(a: float, b: float) -> float:
    """
    两数相减

    Args:
        a: 被减数
        b: 减数

    Returns:
        a - b 的结果
    """
    return a - b


@tool_decorator(category="math", subcategory="basic", tags=["arithmetic", "calculation"])
def multiply(a: float, b: float) -> float:
    """
    两数相乘

    Args:
        a: 第一个数字
        b: 第二个数字

    Returns:
        两数之积
    """
    return a * b


@tool_decorator(category="math", subcategory="basic", tags=["arithmetic", "calculation"])
def divide(a: float, b: float) -> float:
    """
    两数相除

    Args:
        a: 被除数
        b: 除数（不能为 0）

    Returns:
        a / b 的结果

    Raises:
        ValueError: 除数为零时抛出
    """
    if b == 0:
        raise ValueError("Division by zero is not allowed")
    return a / b


@tool_decorator(category="math", subcategory="advanced", tags=["root"])
def sqrt(number: float) -> float:
    """
    平方根

    Args:
        number: 要计算平方根的数

    Returns:
        该数的平方根

    Raises:
        ValueError: 数字为负数时抛出
    """
    if number < 0:
        raise ValueError("Cannot calculate square root of negative number")
    return float(number**0.5)


__all__ = [
    "add",
    "subtract",
    "multiply",
    "divide",
    "sqrt",
]
