"""登录视图（ARCHITECTURE §9.2）。

设计要点
--------

- 表单：用户名 / 密码 / 登录按钮
- 调 :class:`AuthService.login`（通过 :class:`ServiceWorker` 异步）
- 成功 → 触发 :attr:`on_login` 回调
- 失败 → :func:`widgets.error_dialog.show_error`
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from points_v2.core.exceptions import PointsV2Error
from points_v2.core.logging import get_logger
from points_v2.domain.user import User
from points_v2.ui.widgets.error_dialog import show_error
from points_v2.ui.workers import ServiceWorker

__all__ = ["LoginView"]


class LoginView(QWidget):
    """登录表单。"""

    def __init__(
        self,
        services: Any,
        *,
        on_login: Callable[[User], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._services = services
        self._on_login = on_login
        self._log = get_logger("login")
        self._threadpool = services.threadpool  # type: ignore[attr-defined]
        self._pending_worker: ServiceWorker | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)
        outer.setSpacing(12)

        # 标题
        title = QLabel("智能回收社 积分系统 v2")
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        outer.addWidget(title)

        subtitle = QLabel("用户登录")
        subtitle.setStyleSheet("color: #7f8c8d; font-size: 14px;")
        subtitle.setAlignment(Qt.AlignCenter)
        outer.addWidget(subtitle)

        # 表单容器
        form_box = QWidget()
        form_box.setFixedWidth(360)
        form_box.setStyleSheet(
            "QWidget { background: #fff; border-radius: 8px; }"
            "QLineEdit { padding: 8px; border: 1px solid #bdc3c7;"
            "  border-radius: 4px; font-size: 13px; }"
            "QLineEdit:focus { border: 1px solid #1abc9c; }"
            "QPushButton { padding: 10px; background: #1abc9c; color: white;"
            "  border: none; border-radius: 4px; font-size: 14px; font-weight: bold; }"
            "QPushButton:hover { background: #16a085; }"
            "QPushButton:disabled { background: #bdc3c7; }"
        )
        form_layout = QVBoxLayout(form_box)
        form_layout.setContentsMargins(24, 24, 24, 24)
        form_layout.setSpacing(12)

        # 字段
        self._username = QLineEdit()
        self._username.setPlaceholderText("用户名")
        self._username.setMaxLength(32)
        form_layout.addWidget(QLabel("用户名:"))
        form_layout.addWidget(self._username)

        self._password = QLineEdit()
        self._password.setPlaceholderText("密码")
        self._password.setEchoMode(QLineEdit.Password)
        self._password.setMaxLength(128)
        form_layout.addWidget(QLabel("密码:"))
        form_layout.addWidget(self._password)

        self._submit_btn = QPushButton("登录")
        self._submit_btn.setCursor(Qt.PointingHandCursor)
        self._submit_btn.clicked.connect(self._on_submit)
        form_layout.addWidget(self._submit_btn)

        # 回车提交
        self._password.returnPressed.connect(self._on_submit)
        self._username.returnPressed.connect(self._password.setFocus)  # type: ignore[attr-defined]

        # 提示
        self._hint = QLabel("默认管理员: admin / admin123（首次使用请尽快修改密码）")
        self._hint.setStyleSheet("color: #95a5a6; font-size: 11px;")
        self._hint.setWordWrap(True)
        self._hint.setAlignment(Qt.AlignCenter)
        form_layout.addWidget(self._hint)

        # 状态标签
        self._status = QLabel("")
        self._status.setStyleSheet("color: #e74c3c;")
        self._status.setAlignment(Qt.AlignCenter)
        form_layout.addWidget(self._status)

        outer.addWidget(form_box, 0, Qt.AlignCenter)

    # ------------------------------------------------------------------ 槽
    def _on_submit(self) -> None:
        username = self._username.text().strip()
        password = self._password.text()
        if not username:
            self._status.setText("请输入用户名")
            return
        if not password:
            self._status.setText("请输入密码")
            return
        self._set_busy(True)
        self._status.setText("正在登录…")

        # 异步调 auth_service.login
        auth_service = self._services.auth_service
        worker = ServiceWorker(
            auth_service.login,
            username,
            password,
            on_result=self._on_login_result,
            on_error=self._on_login_error,
        )
        self._pending_worker = worker
        self._threadpool.start(worker)

    def _on_login_result(self, token: Any) -> None:
        self._set_busy(False)
        # 用 token 取 user 对象
        try:
            user = self._services.auth_service.verify_token(token.token)
        except PointsV2Error as exc:
            self._status.setText("登录成功但获取用户信息失败")
            show_error(exc, parent=self)
            return
        self._status.setText("登录成功")
        self._password.clear()
        self._on_login(user)

    def _on_login_error(self, exc: Exception) -> None:
        self._set_busy(False)
        self._status.setText("登录失败")
        show_error(exc, title="登录失败", parent=self)

    def _set_busy(self, busy: bool) -> None:
        self._submit_btn.setEnabled(not busy)
        self._username.setEnabled(not busy)
        self._password.setEnabled(not busy)
        self._submit_btn.setText("登录中…" if busy else "登录")

    def reset(self) -> None:
        """退出登录后清空表单。"""
        self._username.clear()
        self._password.clear()
        self._status.setText("")
        self._set_busy(False)
