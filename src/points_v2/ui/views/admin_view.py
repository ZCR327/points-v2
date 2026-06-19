"""管理员视图：审计日志 + 通知广播 + 系统设置（ARCHITECTURE §9.2 "AdminView"）。

布局：3 个 tab —— 审计日志、通知广播、系统设置。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from points_v2.core.logging import get_logger
from points_v2.domain.audit import AuditFilter
from points_v2.domain.enums import NotificationLevel
from points_v2.domain.user import User
from points_v2.ui.widgets.data_table import BaseTableModel, DataTableWidget
from points_v2.ui.widgets.error_dialog import show_error, show_info
from points_v2.ui.workers import ServiceWorker

__all__ = ["AdminView"]


# ---------------------------------------------------------------------------
# 审计日志表模型
# ---------------------------------------------------------------------------
class _AuditLogModel(BaseTableModel):
    COLUMNS = [
        ("时间", "created_at"),
        ("用户 ID", "user_id"),
        ("动作", "action"),
        ("资源", "resource"),
        ("详情", "details"),
        ("IP", "ip_address"),
    ]

    def _row_data(self, row_index: int) -> Any:
        return self._items[row_index]

    def _cell(self, row_index: int, attr: str) -> str:
        rec = self._row_data(row_index)
        val = getattr(rec, attr, "")
        if attr == "created_at":
            return val.strftime("%Y-%m-%d %H:%M:%S") if val else ""
        if attr == "action":
            return getattr(rec, "action_str", str(val))
        if attr == "user_id" and not val:
            return "—"
        if attr == "details" and isinstance(val, dict):
            return ", ".join(f"{k}={v}" for k, v in val.items()) or "—"
        if attr == "ip_address" and not val:
            return "—"
        return str(val) if val is not None else "—"


# ---------------------------------------------------------------------------
# 通知列表模型
# ---------------------------------------------------------------------------
class _NotificationModel(BaseTableModel):
    COLUMNS = [
        ("时间", "created_at"),
        ("级别", "level"),
        ("标题", "title"),
        ("内容", "content"),
        ("用户", "user_id"),
        ("已读", "is_read"),
    ]

    def _row_data(self, row_index: int) -> Any:
        return self._items[row_index]

    def _cell(self, row_index: int, attr: str) -> str:
        rec = self._row_data(row_index)
        val = getattr(rec, attr, "")
        if attr == "created_at":
            return val.strftime("%Y-%m-%d %H:%M:%S") if val else ""
        if attr == "level" and hasattr(val, "value"):
            mapping = {"info": "信息", "warning": "警告", "error": "错误"}
            return mapping.get(val.value, val.value)
        if attr == "user_id" and not val:
            return "全员"
        if attr == "is_read":
            return "✓" if val else "○"
        return str(val) if val is not None else ""


# ---------------------------------------------------------------------------
# AdminView
# ---------------------------------------------------------------------------
class AdminView(QWidget):
    """管理员视图：审计 / 通知 / 设置。"""

    def __init__(self, services: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._services = services
        self._log = get_logger("system")
        self._threadpool = services.threadpool  # type: ignore[attr-defined]
        self._current_user: User | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        # 标题
        title = QLabel("📋 审计 / 通知 / 设置")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        outer.addWidget(title)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_audit_tab(), "🔍 审计日志")
        self._tabs.addTab(self._build_notification_tab(), "🔔 通知广播")
        self._tabs.addTab(self._build_settings_tab(), "⚙️ 系统设置")
        outer.addWidget(self._tabs, 1)

    # ------------------------------------------------------------------ 审计
    def _build_audit_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)

        # 过滤栏
        bar = QHBoxLayout()
        bar.addWidget(QLabel("动作:"))
        self._audit_action = QLineEdit()
        self._audit_action.setPlaceholderText("可选：user.login / points.add …")
        self._audit_action.setMaximumWidth(220)
        bar.addWidget(self._audit_action)
        bar.addWidget(QLabel("用户 ID:"))
        self._audit_user = QLineEdit()
        self._audit_user.setMaximumWidth(220)
        bar.addWidget(self._audit_user)
        bar.addWidget(QLabel("条数:"))
        self._audit_limit = QSpinBox()
        self._audit_limit.setRange(10, 1000)
        self._audit_limit.setValue(100)
        bar.addWidget(self._audit_limit)
        self._audit_query = QPushButton("查询")
        self._audit_query.clicked.connect(self._load_audit)
        bar.addWidget(self._audit_query)
        self._audit_refresh = QPushButton("🔄")
        self._audit_refresh.clicked.connect(self._load_audit)
        bar.addWidget(self._audit_refresh)
        bar.addStretch(1)
        layout.addLayout(bar)

        self._audit_model = _AuditLogModel()
        self._audit_table = DataTableWidget(model=self._audit_model)
        layout.addWidget(self._audit_table, 1)

        self._audit_status = QLabel("")
        self._audit_status.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        layout.addWidget(self._audit_status)
        return widget

    def _load_audit(self) -> None:
        self._audit_refresh.setEnabled(False)
        flt = AuditFilter(
            action=self._audit_action.text().strip() or None,
            user_id=self._audit_user.text().strip() or None,
            limit=self._audit_limit.value(),
        )
        audit_service = self._services.audit_service
        worker = ServiceWorker(
            lambda: audit_service.query(flt),
            on_result=self._on_audit_loaded,
            on_error=self._on_audit_error,
        )
        self._threadpool.start(worker)

    def _on_audit_loaded(self, logs: list[Any]) -> None:
        self._audit_model.set_items(logs)
        self._audit_refresh.setEnabled(True)
        self._audit_status.setText(f"共 {len(logs)} 条")

    def _on_audit_error(self, exc: Exception) -> None:
        self._audit_refresh.setEnabled(True)
        show_error(exc, title="加载审计日志失败", parent=self)

    # ------------------------------------------------------------------ 通知
    def _build_notification_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)

        # 广播表单
        form = QFormLayout()
        self._notif_level = QComboBox()
        for lvl in NotificationLevel:
            self._notif_level.addItem(lvl.value, lvl)
        form.addRow("级别:", self._notif_level)
        self._notif_title = QLineEdit()
        self._notif_title.setMaxLength(200)
        form.addRow("标题:", self._notif_title)
        self._notif_content = QTextEdit()
        self._notif_content.setMaximumHeight(80)
        self._notif_content.setPlaceholderText("通知正文（最多 2000 字符）")
        form.addRow("内容:", self._notif_content)
        self._notif_global = QCheckBox("全员广播（不勾选则仅发给指定用户）")
        self._notif_global.setChecked(True)
        form.addRow("", self._notif_global)
        self._notif_target = QLineEdit()
        self._notif_target.setPlaceholderText("指定用户 ID（仅在未勾选全员时生效）")
        form.addRow("目标用户 ID:", self._notif_target)
        layout.addLayout(form)

        # 按钮
        btn_row = QHBoxLayout()
        self._notif_send = QPushButton("📤 发送")
        self._notif_send.clicked.connect(self._on_send_notification)
        btn_row.addWidget(self._notif_send)
        self._notif_refresh = QPushButton("🔄 刷新通知列表")
        self._notif_refresh.clicked.connect(self._load_notifications)
        btn_row.addWidget(self._notif_refresh)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # 通知列表
        self._notif_model = _NotificationModel()
        self._notif_table = DataTableWidget(model=self._notif_model)
        layout.addWidget(self._notif_table, 1)

        self._notif_status = QLabel("")
        self._notif_status.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        layout.addWidget(self._notif_status)
        return widget

    def _on_send_notification(self) -> None:
        level = self._notif_level.currentData()
        title = self._notif_title.text().strip()
        content = self._notif_content.toPlainText()
        is_global = self._notif_global.isChecked()
        target = self._notif_target.text().strip() or None
        if not title:
            show_info("请填写标题", parent=self)
            return
        if not is_global and not target:
            show_info("非全员广播时必须指定目标用户 ID", parent=self)
            return
        user_id = None if is_global else target
        notification_service = self._services.notification_service
        worker = ServiceWorker(
            lambda: notification_service.create(level, title, content, user_id=user_id),
            on_result=lambda n: self._on_send_done(n),
            on_error=self._on_send_error,
        )
        self._threadpool.start(worker)

    def _on_send_done(self, notif: Any) -> None:
        show_info("通知发送成功", parent=self)
        self._notif_title.clear()
        self._notif_content.clear()
        self._load_notifications()

    def _on_send_error(self, exc: Exception) -> None:
        show_error(exc, title="发送通知失败", parent=self)

    def _load_notifications(self) -> None:
        if self._current_user is None:
            return
        notification_service = self._services.notification_service
        user_id = self._current_user.id
        worker = ServiceWorker(
            lambda: notification_service.list_for_user(user_id, include_global=True, limit=200),
            on_result=self._on_notif_loaded,
            on_error=self._on_notif_error,
        )
        self._threadpool.start(worker)

    def _on_notif_loaded(self, items: list[Any]) -> None:
        # 倒序
        self._notif_model.set_items(sorted(items, key=lambda n: n.created_at, reverse=True))
        self._notif_status.setText(f"共 {len(items)} 条")

    def _on_notif_error(self, exc: Exception) -> None:
        show_error(exc, title="加载通知失败", parent=self)

    # ------------------------------------------------------------------ 设置
    def _build_settings_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)

        # 应用信息
        info_box = QWidget()
        info_box.setStyleSheet(
            "QWidget { background: #fff; border: 1px solid #ecf0f1; border-radius: 4px; }"
        )
        info_layout = QFormLayout(info_box)
        info_layout.setContentsMargins(16, 16, 16, 16)

        from points_v2 import __version__

        info_layout.addRow("应用名称:", QLabel("智能回收社 积分系统 v2"))
        info_layout.addRow("版本:", QLabel(__version__))
        info_layout.addRow("数据目录:", QLabel(str(_data_dir())))
        info_layout.addRow("日志目录:", QLabel(str(_logs_dir())))
        info_layout.addRow(
            "当前时间:", QLabel(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))
        )
        info_layout.addRow(
            "当前用户:", QLabel(self._current_user.display_name if self._current_user else "未登录")
        )
        layout.addWidget(info_box)

        # 占位：未来扩展
        note = QLabel(
            "系统设置目前只读。<br/>"
            "更多配置项（如 API 端口、日志级别）请编辑 <code>config/development.yaml</code> 后重启应用。"
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #7f8c8d; font-size: 12px; padding: 12px;")
        layout.addWidget(note)
        layout.addStretch(1)
        return widget

    # ------------------------------------------------------------------ 入口
    def set_current_user(self, user: User) -> None:
        self._current_user = user
        self.refresh()

    def refresh(self) -> None:
        self._load_audit()
        self._load_notifications()
        # 重建设置 tab 的当前用户显示
        self._tabs.setCurrentIndex(0)


# ---------------------------------------------------------------------------
# 帮助函数：路径
# ---------------------------------------------------------------------------
def _data_dir() -> Any:
    from points_v2.core import paths

    return paths.DATA_DIR


def _logs_dir() -> Any:
    from points_v2.core import paths

    return paths.LOGS_DIR
