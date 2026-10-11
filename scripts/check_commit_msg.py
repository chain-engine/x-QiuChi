#!/usr/bin/env python3
"""Conventional Commits 提交信息校验（commit-msg 钩子调用）。

规则（精简版 Conventional Commits 1.0）：
    <type>[optional scope]: <subject>
    type ∈ feat | fix | refactor | docs | style | test | chore | perf | build | ci | revert

自动放行：
    - 合并 / 还原提交（"Merge ..." / "Revert ..."）
    - rebase --autosquash 生成（"fixup! ..." / "squash! ..."）
    - 空提交信息（防呆）

用法：
    python scripts/check_commit_msg.py <commit-msg-file>

说明：subject 不强制语言/大小写（项目支持中文信息），仅约束结构与长度，
保证每条提交可回溯"做了什么、为什么"。跳过校验：git commit --no-verify。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# 合法类型（覆盖项目常见提交：feat / fix / refactor / docs / test / chore / build）
TYPES = frozenset(
    {
        "feat",
        "fix",
        "refactor",
        "docs",
        "style",
        "test",
        "chore",
        "perf",
        "build",
        "ci",
        "revert",
    }
)

# type(scope)!: subject 或 type: subject（scope 允许 [a-z0-9._/-]）
_PATTERN = re.compile(
    r"^(?P<type>[a-z]+)(?:\((?P<scope>[a-z0-9._/-]+)\))?!?: (?P<subject>.+)$"
)

# 与 pyproject ruff line-length 对齐
_MAX_SUBJECT_LEN = 100

# 自动生成的提交信息前缀，不做格式校验
_AUTO_PREFIXES = ("Merge ", "Revert ", "fixup! ", "squash! ")


def _validate(message: str) -> list[str]:
    """返回违规描述列表；为空表示通过。"""
    errors: list[str] = []
    first_line = message.splitlines()[0].strip() if message else ""

    if not message:
        return errors
    if first_line.startswith(_AUTO_PREFIXES):
        return errors

    match = _PATTERN.match(first_line)
    if not match:
        errors.append(
            "提交信息不符合 Conventional Commits 格式：\n"
            f"    实际: {first_line!r}\n"
            "    期望: <type>[optional scope]: <subject>\n"
            f"    type ∈ {' | '.join(sorted(TYPES))}\n"
            "    示例: feat(auth): add bearer token verification"
        )
        return errors

    if match.group("type") not in TYPES:
        errors.append(
            f"未知 type '{match.group('type')}'。"
            f"合法 type: {' | '.join(sorted(TYPES))}"
        )
        return errors

    subject = match.group("subject")
    if len(subject) > _MAX_SUBJECT_LEN:
        errors.append(
            f"subject 过长（{len(subject)} > {_MAX_SUBJECT_LEN} 字符），"
            "请精简到一行以内，细节写入 body。"
        )
    return errors


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: check_commit_msg.py <commit-msg-file>", file=sys.stderr)
        return 1

    msg_path = Path(sys.argv[1])
    message = msg_path.read_text(encoding="utf-8")

    errors = _validate(message)
    if errors:
        print("commit-msg: 提交被拒绝：", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        print(
            "  跳过校验（不推荐）: git commit --no-verify",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
