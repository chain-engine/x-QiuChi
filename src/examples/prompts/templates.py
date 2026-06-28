"""
提示词模板示例

展示如何使用 QiuChi 的提示词装饰器创建提示词模板。
"""

from src import prompt


@prompt(category="greeting", tags=["welcome", "social"])
def greeting(name: str) -> str:
    """
    生成问候语

    Args:
        name: 用户名

    Returns:
        个性化的问候语
    """
    return f"Hello, {name}! Welcome to QiuChi MCP Server. How can I assist you today?"


@prompt(category="code", tags=["development", "review"])
def code_review(language: str, code_snippet: str) -> str:
    """
    生成代码审查提示

    Args:
        language: 编程语言
        code_snippet: 代码片段

    Returns:
        代码审查提示
    """
    return f"""Please review the following {language} code for best practices, potential bugs, and performance issues:

```{language}
{code_snippet}
```

Please provide:
1. Code quality assessment
2. Potential bugs or edge cases
3. Performance considerations
4. Suggested improvements
5. Security concerns (if any)"""


@prompt(category="weather", tags=["advice", "daily"])
def weather_outfit_advice(weather: str, temperature: float) -> str:
    """
    生成天气穿衣建议

    Args:
        weather: 天气状况 (sunny, rainy, cloudy, snowy)
        temperature: 温度（摄氏度）

    Returns:
        穿衣建议提示
    """
    return f"""Based on the current weather ({weather}, {temperature}°C), here's my outfit advice:

1. **Temperature consideration**: {temperature}°C is {'very cold' if temperature < 0 else 'cold' if temperature < 10 else 'cool' if temperature < 20 else 'warm' if temperature < 30 else 'hot'}.
2. **Weather-specific advice**: {{
    'sunny': 'Wear sunglasses and apply sunscreen',
    'rainy': 'Bring an umbrella and wear waterproof shoes',
    'cloudy': 'Layers are recommended as it might get chilly',
    'snowy': 'Wear insulated clothing and waterproof boots'
    }}.get(weather, 'Dress appropriately for the conditions')
3. **Recommended clothing**: Suggest appropriate clothing based on both temperature and weather.

Please provide specific clothing recommendations."""


@prompt(category="education", tags=["learning", "explanation"])
def explain_concept(concept: str, audience: str = "beginner") -> str:
    """
    生成概念解释提示

    Args:
        concept: 要解释的概念
        audience: 目标受众 (beginner, intermediate, advanced)

    Returns:
        概念解释提示
    """
    return f"""Please explain the concept of "{concept}" to a {audience} audience.

Requirements:
1. Start with a simple, clear definition
2. Use analogies or examples appropriate for a {audience}
3. Explain why this concept is important
4. Provide practical applications or use cases
5. Mention any common misconceptions
6. Keep the explanation concise but comprehensive

Target audience: {audience}"""


@prompt(category="documentation", tags=["summary", "analysis"])
def summarize_document(document: str, max_length: int = 200) -> str:
    """
    生成文档摘要提示

    Args:
        document: 要摘要的文档
        max_length: 摘要的最大长度

    Returns:
        文档摘要提示
    """
    return f"""Please summarize the following document in under {max_length} words:

{document}

Summary requirements:
1. Capture the main points and key information
2. Maintain the original meaning and context
3. Use clear, concise language
4. Highlight any important conclusions or recommendations
5. Keep the summary under {max_length} words

Provide only the summary, without additional commentary."""


__all__ = [
    "greeting",
    "code_review",
    "weather_outfit_advice",
    "explain_concept",
    "summarize_document",
]