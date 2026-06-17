"""统一错误弹窗（ARCHITECTURE §4.2 "统一错误处理"）。

设计要点
--------

- :func:`show_error` 把任意 :class:`Exception` 显示为中文 QMessageBox
- :class:`PointsV2Error` 用 ``self.message`` 字段；其他用 ``str(exc)``
- ``details`` 字段（如果有）一并展示
- 父窗口 ``parent`` 用于居中显示
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QMessageBox, QWidget

from points_v2.core.exceptions import PointsV2Error

__all__ = ["show_error", "show_warning", "show_info"]


def _format_message(exc: BaseException) -> str:
    if isinstance(exc, PointsV2Error):
        msg = exc.message or str(exc)
        if exc.details:
            msg += "\n\n详细信息:\n" + "\n".join(
                f"  • {k}: {v}" for k, v in exc.details.items()
            )
        return msg
    return str(exc) or exc.__class__.__name__


def show_error(
    exc: BaseException,
    *,
    title: str = "错误",
    parent: QWidget | None = None,
) -> None:
    """显示一个红色错误弹窗。"""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Critical)
    box.setWindowTitle(title)
    box.setText(_format_message(exc))
    box.setStandardButtons(QMessageBox.Ok)
    box.setDefaultButton(QMessageBox.Ok)
    box.exec()


def show_warning(
    message: str,
    *,
    title: str = "提示",
    parent: QWidget | None = None,
) -> None:
    """显示黄色警告弹窗。"""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle(title)
    box.setText(message)
    box.setStandardButtons(QMessageBox.Ok)
    box.exec()


def show_info(
    message: str,
    *,
    title: str = "提示",
    parent: QWidget | None = None,
) -> None:
    """显示蓝色信息弹窗。"""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Information)
    box.setWindowTitle(title)
    box.setText(message)
    box.setStandardButtons(QMessageBox.Ok)
    box.exec()


def ask_confirm(
    message: str,
    *,
    title: str = "确认",
    parent: QWidget | None = None,
    default_yes: bool = False,
) -> bool:
    """显示 Yes/No 确认弹窗，返回 True 表示用户选 Yes。"""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Question)
    box.setWindowTitle(title)
    box.setText(message)
    box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    box.setDefaultButton(QMessageBox.Yes if default_yes else QMessageBox.No)
    return box.exec() == QMessageBox.Yes


# 兼容旧名：show_error_box 别名
def show_error_box(
    message: str,
    *,
    title: str = "错误",
    parent: QWidget | None = None,
) -> None:
    """按字符串显示错误弹窗。"""
    exc = PointsV2Error(message) if not isinstance(message, BaseException) else message  # type: ignore[arg-type]
    show_error(exc, title=title, parent=parent)


# 显式把 ``Any`` 当作已使用（避免 ruff 报 unused import）
_ = Any
