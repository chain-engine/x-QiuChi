#!/usr/bin/env python3
"""可描述枚举基类。

为枚举成员附加 mark（唯一标识）和 desc（描述信息），
使枚举可直接与 str/int 比较，并兼容 Pydantic 序列化。
"""

from enum import Enum


class BaseEnum(Enum):
    """可描述枚举基类。

    每个成员持有两个属性：
        mark: 唯一标识（int 或 str），用于数据库存储和序列化
        desc: 人类可读的描述信息
    """

    def __init__(self, mark: int | str, desc: str) -> None:
        self._mark = mark
        self._desc = desc

    @property
    def mark(self) -> int | str:
        """枚举唯一标识。"""
        return self._mark

    @property
    def value(self) -> str:
        """重写 value，使枚举可直接赋值给 str 类型字段（如 Pydantic BaseModel）。"""
        return str(self._mark)

    @property
    def desc(self) -> str:
        """人类可读的描述信息。"""
        return self._desc

    def __str__(self) -> str:
        return str(self._mark)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Enum):
            return super().__eq__(other)
        if isinstance(other, str):
            return self._mark == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._mark)

    @classmethod
    def get_all_marks(cls) -> list[int | str]:
        """获取所有枚举成员的 mark 列表。"""
        return [member.mark for member in cls]

    @classmethod
    def get_all_descs(cls) -> list[str]:
        return [described_enum.desc for described_enum in cls]

    @classmethod
    def get_choices(cls) -> tuple[tuple[int | str, str], ...]:
        return tuple((described_enum.mark, described_enum.desc) for described_enum in cls)
