"""UI smoke test — 验证 UI 可以启动 + 不真显示窗口（offscreen 模式）。

设计要点
--------

- 通过 ``QT_QPA_PLATFORM=offscreen`` 跳过真实平台插件（CI 友好）
- 验证 ``MainWindow`` 可以构造 + show + processEvents（不崩）
- 不测试业务逻辑（service 层有专门测试）
- 用 :func:`build_default_services` 拿最小依赖
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

# 必须在 import PySide6 之前设置 offscreen
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qt_app() -> Iterator[object]:
    """创建 QApplication 单例（module 级别，节省时间）。"""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(["points_v2-test"])
    yield app
    # 不 quit（让 pytest 结束自然清理）


@pytest.fixture
def services(tmp_data_dir, qt_app: object) -> object:
    """最小 service bundle（用 tmp_data_dir 隔离）。"""
    from points_v2.api.app_state import build_default_services

    return build_default_services()


def test_create_qt_app_returns_instance(qt_app: object) -> None:
    """QApplication 单例存在。"""
    from PySide6.QtWidgets import QApplication

    assert isinstance(qt_app, QApplication)


def test_main_window_constructs_and_shows(qt_app: object, services: object) -> None:
    """MainWindow 可以构造 + show + processEvents 不崩。"""
    from points_v2.ui.main_window import MainWindow

    window = MainWindow(services=services)
    assert window.windowTitle() == "智能回收社 积分系统 v2"
    window.show()
    qt_app.processEvents()  # type: ignore[attr-defined]
    # 验证 default 页面是 login（currentIndex == 0）
    assert window.isVisible()


def test_login_view_in_stack(qt_app: object, services: object) -> None:
    """LoginView 已经在 stacked widget 中（index 0）。"""
    from points_v2.ui.main_window import MainWindow
    from points_v2.ui.views.login_view import LoginView

    window = MainWindow(services=services)
    central = window.centralWidget()
    assert central is not None
    # LoginView 应该是 stacked 第一个
    login_widget = central.widget(0) if hasattr(central, "widget") else None
    assert login_widget is not None
    assert isinstance(login_widget, LoginView)


def test_workers_module_imports() -> None:
    """workers 模块不依赖 Qt 平台（不需要 qt_app）。"""
    from points_v2.ui.workers import ServiceWorker, WorkerSignals

    assert ServiceWorker is not None
    assert WorkerSignals is not None


def test_widgets_error_dialog_imports() -> None:
    """error_dialog 模块导出齐全。"""
    from points_v2.ui.widgets.error_dialog import (
        ask_confirm,
        show_error,
        show_info,
        show_warning,
    )

    assert callable(show_error)
    assert callable(show_warning)
    assert callable(show_info)
    assert callable(ask_confirm)


def test_widgets_chart_imports() -> None:
    """chart_widget 模块导出齐全。"""
    from points_v2.ui.widgets.chart_widget import ChartWidget

    assert ChartWidget is not None


def test_widgets_data_table_imports() -> None:
    """data_table 模块导出齐全。"""
    from points_v2.ui.widgets.data_table import BaseTableModel, DataTableWidget, RowListModel

    assert BaseTableModel is not None
    assert DataTableWidget is not None
    assert RowListModel is not None


def test_views_imports() -> None:
    """5 个 view 都能 import（不实际构造）。"""
    from points_v2.ui.views.admin_view import AdminView
    from points_v2.ui.views.dashboard_view import DashboardView
    from points_v2.ui.views.login_view import LoginView
    from points_v2.ui.views.points_view import PointsView
    from points_v2.ui.views.user_view import UserView

    assert all((LoginView, DashboardView, PointsView, UserView, AdminView))
