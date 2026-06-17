"""Time helpers — 统一 UTC，避免本地时区歧义（ARCHITECTURE §5.1）。

设计要点
--------

- 所有持久化时间字段都用 **UTC datetime with tzinfo**
- ``format_datetime`` 输出 ISO-8601（带 ``Z`` 后缀便于阅读）；UI 层可再格式化
- ``parse_datetime`` 接受 ISO 字符串 / datetime / None；缺省返回当前 UTC

为什么不用 ``datetime.utcnow()``
--------------------------------
``utcnow()`` 在 Python 3.12+ 已弃用，且返回 **naive** datetime（无 tzinfo）。
统一用 :func:`datetime.now(timezone.utc)` 拿到 aware datetime，
序列化时不会出现 5 小时偏移的诡异 bug（学生血泪）。
"""

from __future__ import annotations

from datetime import datetime, timezone

__all__ = ["utcnow", "format_datetime", "parse_datetime"]


def utcnow() -> datetime:
    """返回带 UTC 时区的 ``datetime``（aware）。"""
    return datetime.now(timezone.utc)


def format_datetime(value: datetime | None, *, with_z: bool = True) -> str:
    """把 datetime 格式化成 ISO-8601 字符串。

    :param value: 要格式化的 datetime；``None`` 返回 ``""``。
    :param with_z: ``True`` 把 ``+00:00`` 改写成 ``Z``（更紧凑、UI 友好）。
    :returns: ISO-8601 字符串。
    """
    if value is None:
        return ""
    # 已是 aware 直接序列化；naive 视为 UTC（兼容遗留数据）
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    text = value.isoformat()
    if with_z and text.endswith("+00:00"):
        return text[:-6] + "Z"
    return text


def parse_datetime(value: datetime | str | None) -> datetime | None:
    """把 ISO-8601 字符串 / datetime 转成 UTC-aware datetime。

    - ``None`` → ``None``
    - ``datetime`` 实例：naive 视为 UTC；aware 转 UTC
    - 字符串：支持 ``Z`` 后缀 / ``+00:00`` / naive（视为 UTC）
    - 解析失败 → :class:`ValueError`

    :returns: UTC-aware datetime 或 ``None``。
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        # Python 3.11+ 原生支持 Z 后缀；3.10 也支持（3.11 之前需要替换）
        # 这里用 fromisoformat 一把搞定；处理两种尾巴
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(
                f"parse_datetime: 无法解析时间字符串 {value!r}",
            ) from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    raise TypeError(
        f"parse_datetime: 期望 datetime / str / None，实际 {type(value).__name__}",
    )
