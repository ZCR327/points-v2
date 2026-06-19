"""QMainWindow：顶部栏 + 侧边栏 + QStackedWidget + 状态栏（ARCHITECTURE §9.1）。

设计要点
--------

- 顶部栏：应用名 + 当前用户 + 退出按钮
- 侧边栏：导航按钮（概览 / 积分 / 用户 / 审计 / 通知 / 设置）
- 中心：``QStackedWidget``，按导航切换 :class:`QWidget` 视图
- 状态栏：当前时间 + 任务进度（``QProgressBar`` 隐藏备用）
- 登录态管理：未登录显示 :class:`LoginView`；登录后切到主界面
- **服务注入**：构造函数接收 :class:`ServiceBundle`（来自 ``api.app_state``），
  每个 view 也接收 bundle —— 测试时用 fake bundle 隔离
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

from PySide6.QtCore import QSize, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from points_v2.core.logging import get_logger
from points_v2.domain.user import User
from points_v2.ui.views.admin_view import AdminView
from points_v2.ui.views.dashboard_view import DashboardView
from points_v2.ui.views.login_view import LoginView
from points_v2.ui.views.points_view import PointsView
from points_v2.ui.views.user_view import UserView

__all__ = ["MainWindow"]


class MainWindow(QMainWindow):
    """主窗口（ARCHITECTURE §9.1）。"""

    def __init__(self, services: Any | None = None, *, parent: QWidget | None = None) -> None:
        """构造主窗口。

        :param services: 已构造的 :class:`ServiceBundle`；传 ``None`` 时本构造器会
            延迟调用 :func:`build_default_services`，便于 smoke test / 单文件
            ``python -c "from points_v2.ui.main_window import MainWindow; MainWindow()"``
            这种用法。
        :param parent: 父 QWidget（可选）。
        """
        super().__init__(parent)
        if services is None:
            from points_v2.api.app_state import build_default_services

            services = build_default_services()
        self._services = services
        self._log = get_logger("system")
        self._current_user: User | None = None
        self._threadpool = getattr(services, "threadpool", None)

        self.setWindowTitle("智能回收社 积分系统 v2")
        self.resize(1200, 800)
        self.setMinimumSize(QSize(900, 600))

        # 中心 stacked widget
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # 视图（在 _build_views 中按需构造）
        self._login_view: LoginView | None = None
        self._dashboard_view: DashboardView | None = None
        self._points_view: PointsView | None = None
        self._user_view: UserView | None = None
        self._admin_view: AdminView | None = None
        self._main_shell: QWidget | None = None  # 登录后的主界面（带侧边栏）

        # 状态栏
        self._build_status_bar()
        # 顶部栏 + 侧边栏 + 内容
        self._build_main_shell()
        # 登录视图（独立于 main_shell）
        self._login_view = LoginView(services=services, on_login=self._on_login)
        self._stack.addWidget(self._login_view)  # index 0
        self._stack.addWidget(self._main_shell)  # index 1

        # 时钟
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

        # 默认显示登录页
        self._show_login()

    # ------------------------------------------------------------------ 构建
    def _build_status_bar(self) -> None:
        """底部状态栏：左侧文字、右侧时间。"""
        bar = QStatusBar()
        self.setStatusBar(bar)
        self._status_label = QLabel("就绪")
        self._status_progress = QProgressBar()
        self._status_progress.setMaximumWidth(180)
        self._status_progress.setRange(0, 0)  # busy indicator
        self._status_progress.setVisible(False)
        self._status_progress.setTextVisible(False)
        self._clock_label = QLabel("")
        self._clock_label.setStyleSheet("color: #666; padding: 0 8px;")
        bar.addWidget(self._status_label, 1)
        bar.addPermanentWidget(self._status_progress)
        bar.addPermanentWidget(self._clock_label)

    def _build_main_shell(self) -> None:
        """登录后的主界面：顶部栏 + 侧边栏 + 中心 stacked。"""
        self._main_shell = QWidget()
        outer = QVBoxLayout(self._main_shell)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 顶部栏
        top_bar = self._build_top_bar()
        outer.addWidget(top_bar)
        # 提前初始化侧边栏按钮列表（_build_sidebar 会 append）
        self._sidebar_buttons = []

        # 中间：侧边栏 + 内容
        middle = QHBoxLayout()
        middle.setContentsMargins(0, 0, 0, 0)
        middle.setSpacing(0)
        sidebar = self._build_sidebar()
        middle.addWidget(sidebar)

        # 中心 stacked（与主 stacked 分开，避免登录/主界面冲突）
        self._inner_stack = QStackedWidget()
        self._inner_stack.setObjectName("innerStack")
        self._dashboard_view = DashboardView(services=self._services)
        self._points_view = PointsView(services=self._services)
        self._user_view = UserView(services=self._services)
        self._admin_view = AdminView(services=self._services)
        self._inner_stack.addWidget(self._dashboard_view)  # 0
        self._inner_stack.addWidget(self._points_view)  # 1
        self._inner_stack.addWidget(self._user_view)  # 2
        self._inner_stack.addWidget(self._admin_view)  # 3
        middle.addWidget(self._inner_stack, 1)

        outer.addLayout(middle, 1)

        # 侧边栏按钮 → 切换 inner_stack（_sidebar_buttons 已在方法开头初始化）

    def _build_top_bar(self) -> QFrame:
        """顶部栏：应用名 + 副标题 + 当前用户 + 退出按钮。"""
        bar = QFrame()
        bar.setObjectName("topBar")
        bar.setStyleSheet(
            "QFrame#topBar { background: #2c3e50; color: #ecf0f1; }"
            "QFrame#topBar QLabel { color: #ecf0f1; }"
        )
        bar.setFixedHeight(56)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        title = QLabel("智能回收社 积分系统 v2")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        subtitle = QLabel("PySide6 桌面端")
        subtitle.setStyleSheet("color: #bdc3c7;")
        layout.addWidget(subtitle)
        layout.addStretch(1)

        self._user_label = QLabel("未登录")
        self._user_label.setStyleSheet("padding: 0 12px;")
        layout.addWidget(self._user_label)

        self._logout_btn = QPushButton("退出")
        self._logout_btn.setObjectName("logoutBtn")
        self._logout_btn.setFixedWidth(72)
        self._logout_btn.clicked.connect(self._on_logout)
        self._logout_btn.setEnabled(False)
        layout.addWidget(self._logout_btn)
        return bar

    def _build_sidebar(self) -> QFrame:
        """侧边栏：导航按钮（垂直排列）。"""
        bar = QFrame()
        bar.setObjectName("sidebar")
        bar.setStyleSheet(
            "QFrame#sidebar { background: #34495e; }"
            "QFrame#sidebar QPushButton {"
            "  background: transparent; color: #ecf0f1; border: none;"
            "  padding: 12px 16px; text-align: left; font-size: 13px;"
            "}"
            "QFrame#sidebar QPushButton:hover { background: #2c3e50; }"
            "QFrame#sidebar QPushButton:checked { background: #1abc9c; color: #fff; }"
        )
        bar.setFixedWidth(180)
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(2)

        nav_items = [
            ("📊 概览", 0),
            ("💰 积分", 1),
            ("👥 用户", 2),
            ("📋 审计 / 通知", 3),
        ]
        for label, idx in nav_items:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setProperty("viewIndex", idx)
            if idx == 0:
                btn.setChecked(True)
            btn.clicked.connect(self._on_sidebar_clicked)
            self._sidebar_buttons.append(btn)
            layout.addWidget(btn)
        layout.addStretch(1)
        return bar

    # ------------------------------------------------------------------ 槽
    def _on_sidebar_clicked(self) -> None:
        sender = self.sender()
        if not isinstance(sender, QPushButton):
            return
        idx = sender.property("viewIndex")
        if not isinstance(idx, int):
            return
        # 同步其他按钮的 checked 状态
        for i, btn in enumerate(self._sidebar_buttons):
            btn.setChecked(i == idx)
        self._inner_stack.setCurrentIndex(idx)

    def _on_login(self, user: User) -> None:
        """登录成功回调。"""
        self._current_user = user
        self._user_label.setText(f"👤 {user.display_name}（{user.role.value}）")
        self._logout_btn.setEnabled(True)
        self._log.info("UI 登录", user_id=user.id, username=user.username)
        self._show_main()
        # 通知 dashboard / points 视图刷新
        if self._dashboard_view is not None:
            self._dashboard_view.refresh()
        if self._points_view is not None:
            self._points_view.set_current_user(user)
        if self._user_view is not None:
            self._user_view.set_current_user(user)
        if self._admin_view is not None:
            self._admin_view.set_current_user(user)

    def _on_logout(self) -> None:
        """退出登录：清状态 + 回到登录页。"""
        confirm = QMessageBox.question(
            self,
            "确认退出",
            "确定要退出登录吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        self._current_user = None
        self._user_label.setText("未登录")
        self._logout_btn.setEnabled(False)
        if self._login_view is not None:
            self._login_view.reset()
        self._show_login()
        self._log.info("UI 退出登录")

    def _show_login(self) -> None:
        self._stack.setCurrentIndex(0)

    def _show_main(self) -> None:
        self._stack.setCurrentIndex(1)

    # ------------------------------------------------------------------ 状态
    def _update_clock(self) -> None:
        now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._clock_label.setText(f"🕐 {now}")

    def set_status(self, message: str) -> None:
        """对外暴露的状态栏设置。"""
        self._status_label.setText(message)

    def set_busy(self, busy: bool) -> None:
        """显示/隐藏忙碌指示器。"""
        self._status_progress.setVisible(busy)
        if busy:
            self._status_label.setText("处理中…")
        else:
            self._status_label.setText("就绪")

    # ------------------------------------------------------------------ 退出
    def shutdown(self) -> None:
        """窗口关闭时清理资源。"""
        try:
            # 等待所有 QRunnable 完成
            if self._threadpool is not None:
                self._threadpool.waitForDone(2000)  # 最多等 2 秒
        except Exception:  # noqa: BLE001
            pass
        self._log.info("UI 关闭")

    def closeEvent(self, event: Any) -> None:  # noqa: N802 - Qt 命名
        """窗口关闭事件：复用 shutdown。"""
        self.shutdown()
        super().closeEvent(event)

    # ------------------------------------------------------------------ 访问
    @property
    def current_user(self) -> User | None:
        return self._current_user
