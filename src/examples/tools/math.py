"""
数学工具示例

展示如何使用 QiuChi 的装饰器 API 创建工具。
"""

from src import tool


@tool(category="math", subcategory="basic", tags=["arithmetic", "calculation"])
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


@tool(category="math", subcategory="basic", tags=["arithmetic", "calculation"])
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


@tool(category="math", subcategory="basic", tags=["arithmetic", "calculation"])
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


@tool(category="math", subcategory="basic", tags=["arithmetic", "calculation"])
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


@tool(category="math", subcategory="advanced", tags=["exponentiation"])
def power(base: float, exponent: float) -> float:
    """
    幂运算

    Args:
        base: 底数
        exponent: 指数

    Returns:
        base 的 exponent 次方
    """
    return base ** exponent


@tool(category="math", subcategory="advanced", tags=["root"])
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
    return number ** 0.5


@tool(category="conversion", tags=["temperature"])
def celsius_to_fahrenheit(celsius: float) -> float:
    """
    摄氏度转华氏度

    Args:
        celsius: 摄氏度

    Returns:
        对应的华氏度
    """
    return (celsius * 9/5) + 32


@tool(category="conversion", tags=["temperature"])
def fahrenheit_to_celsius(fahrenheit: float) -> float:
    """
    华氏度转摄氏度

    Args:
        fahrenheit: 华氏度

    Returns:
        对应的摄氏度
    """
    return (fahrenheit - 32) * 5/9


__all__ = [
    "add",
    "subtract",
    "multiply",
    "divide",
    "power",
    "sqrt",
    "celsius_to_fahrenheit",
    "fahrenheit_to_celsius",
]