"""积分流水视图（ARCHITECTURE §9.2 "PointsView"）。

布局：积分流水表 + 加减按钮。
"""

from __future__ import annotations

from typing import Any

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from points_v2.core.exceptions import InsufficientPointsError
from points_v2.core.logging import get_logger
from points_v2.domain.user import User
from points_v2.ui.widgets.data_table import BaseTableModel, DataTableWidget
from points_v2.ui.widgets.error_dialog import show_error, show_info
from points_v2.ui.workers import ServiceWorker

__all__ = ["PointsView"]


class _PointsRecordModel(BaseTableModel):
    """积分流水表模型。"""

    COLUMNS = [
        ("时间", "created_at"),
        ("用户", "user_id"),
        ("操作", "operation"),
        ("金额", "amount"),
        ("余额", "balance_after"),
        ("原因", "reason"),
        ("操作员", "operator_id"),
    ]

    def _row_data(self, row_index: int) -> Any:
        return self._items[row_index]

    def _cell(self, row_index: int, attr: str) -> str:
        rec = self._row_data(row_index)
        val = getattr(rec, attr, "")
        if attr == "operation" and hasattr(val, "value"):
            # 翻译成中文
            mapping = {
                "earn": "回收获得",
                "spend": "商城消费",
                "transfer_in": "转入",
                "transfer_out": "转出",
                "adjust": "管理员调整",
                "refund": "退款",
            }
            return mapping.get(val.value, val.value)
        if attr == "created_at":
            return val.strftime("%Y-%m-%d %H:%M:%S") if val else ""
        if attr == "operator_id":
            return val or "系统"
        return str(val)


class _PointsAdjustDialog(QDialog):
    """加减积分对话框。"""

    def __init__(
        self,
        *,
        users: list[User],
        mode: str,  # "add" or "deduct"
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._mode = mode
        self.setWindowTitle("加积分" if mode == "add" else "扣积分")
        self.setMinimumWidth(360)

        layout = QFormLayout(self)

        self._user = QComboBox()
        for u in users:
            self._user.addItem(f"{u.display_name}（{u.username} · {u.points} 分）", u.id)
        layout.addRow("用户:", self._user)

        self._amount = QSpinBox()
        self._amount.setRange(1, 1_000_000_000)
        self._amount.setValue(10)
        layout.addRow("积分:", self._amount)

        self._reason = QLineEdit()
        self._reason.setPlaceholderText("可选：如「回收纸板」「商城兑换」")
        self._reason.setMaxLength(500)
        layout.addRow("原因:", self._reason)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def selected_user_id(self) -> str:
        return self._user.currentData() or ""

    def amount(self) -> int:
        return self._amount.value()

    def reason(self) -> str:
        return self._reason.text().strip()


class PointsView(QWidget):
    """积分流水 + 加减操作。"""

    def __init__(self, services: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._services = services
        self._log = get_logger("points")
        self._threadpool = services.threadpool  # type: ignore[attr-defined]
        self._current_user: User | None = None
        self._users: list[User] = []
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        # 标题栏
        header = QHBoxLayout()
        title = QLabel("💰 积分流水")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        header.addWidget(title)
        header.addStretch(1)

        self._filter_user = QComboBox()
        self._filter_user.setMinimumWidth(220)
        self._filter_user.currentIndexChanged.connect(self._on_filter_changed)
        header.addWidget(QLabel("用户:"))
        header.addWidget(self._filter_user)

        self._add_btn = QPushButton("➕ 加积分")
        self._add_btn.clicked.connect(lambda: self._on_adjust("add"))
        header.addWidget(self._add_btn)
        self._deduct_btn = QPushButton("➖ 扣积分")
        self._deduct_btn.clicked.connect(lambda: self._on_adjust("deduct"))
        header.addWidget(self._deduct_btn)
        self._refresh_btn = QPushButton("🔄 刷新")
        self._refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self._refresh_btn)
        outer.addLayout(header)

        # 数据表
        self._model = _PointsRecordModel()
        self._table = DataTableWidget(model=self._model)
        outer.addWidget(self._table, 1)

        self._status = QLabel("")
        self._status.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        outer.addWidget(self._status)

    def set_current_user(self, user: User) -> None:
        self._current_user = user
        self.refresh()

    def refresh(self) -> None:
        """重新加载用户列表 + 当前选中用户的流水。"""
        self._refresh_btn.setEnabled(False)
        self._status.setText("加载中…")
        # 1) 加载用户
        user_service = self._services.user_service
        worker = ServiceWorker(
            lambda: user_service.list(offset=0, limit=500),
            on_result=self._on_users_loaded,
            on_error=self._on_users_error,
        )
        self._threadpool.start(worker)

    def _on_users_loaded(self, users: list[User]) -> None:
        self._users = users
        # 重建 filter 下拉框
        self._filter_user.blockSignals(True)
        self._filter_user.clear()
        self._filter_user.addItem("（所有用户）", "")
        for u in users:
            self._filter_user.addItem(f"{u.display_name}（{u.username}）", u.id)
        # 优先选当前用户
        if self._current_user is not None:
            for i in range(self._filter_user.count()):
                if self._filter_user.itemData(i) == self._current_user.id:
                    self._filter_user.setCurrentIndex(i)
                    break
        self._filter_user.blockSignals(False)
        # 加载流水
        self._load_history()

    def _on_users_error(self, exc: Exception) -> None:
        self._refresh_btn.setEnabled(True)
        self._status.setText("用户列表加载失败")
        show_error(exc, title="加载用户失败", parent=self)

    def _on_filter_changed(self, _idx: int) -> None:
        self._load_history()

    def _load_history(self) -> None:
        user_id = self._filter_user.currentData() or None
        points_service = self._services.points_service
        if user_id:
            worker = ServiceWorker(
                lambda: points_service.get_history(user_id, days=None, limit=500),
                on_result=self._on_history,
                on_error=self._on_history_error,
            )
        else:
            # 所有用户 → 拉所有流水
            worker = ServiceWorker(
                lambda: points_service._points_repo.all(),  # type: ignore[attr-defined]
                on_result=lambda recs: self._on_history(list(recs)),
                on_error=self._on_history_error,
            )
        self._threadpool.start(worker)

    def _on_history(self, records: list[Any]) -> None:
        # 按时间倒序
        records_sorted = sorted(records, key=lambda r: r.created_at, reverse=True)
        self._model.set_items(records_sorted)
        self._refresh_btn.setEnabled(True)
        self._status.setText(f"共 {len(records_sorted)} 条流水")

    def _on_history_error(self, exc: Exception) -> None:
        self._refresh_btn.setEnabled(True)
        self._status.setText("流水加载失败")
        show_error(exc, title="加载流水失败", parent=self)

    # ------------------------------------------------------------------ 加减
    def _on_adjust(self, mode: str) -> None:
        if not self._users:
            show_info("请先刷新用户列表", parent=self)
            return
        dlg = _PointsAdjustDialog(users=self._users, mode=mode, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        user_id = dlg.selected_user_id()
        amount = dlg.amount()
        reason = dlg.reason() or ("管理员加积分" if mode == "add" else "管理员扣积分")
        self._do_adjust(user_id, amount, reason, mode)

    def _do_adjust(self, user_id: str, amount: int, reason: str, mode: str) -> None:
        points_service = self._services.points_service
        operator_id = self._current_user.id if self._current_user else None

        def add_fn() -> Any:
            return points_service.add(user_id, amount, reason, operator_id)

        def deduct_fn() -> Any:
            return points_service.deduct(user_id, amount, reason, operator_id)

        fn = add_fn if mode == "add" else deduct_fn
        self._set_busy(True)
        worker = ServiceWorker(
            fn,
            on_result=lambda rec: self._on_adjust_done(rec, mode),
            on_error=self._on_adjust_error,
        )
        self._threadpool.start(worker)

    def _on_adjust_done(self, rec: Any, mode: str) -> None:
        self._set_busy(False)
        show_info(f"操作成功！新余额：{rec.balance_after} 分", parent=self)
        self.refresh()

    def _on_adjust_error(self, exc: Exception) -> None:
        self._set_busy(False)
        if isinstance(exc, InsufficientPointsError):
            show_error(exc, title="积分不足", parent=self)
        else:
            show_error(exc, title="操作失败", parent=self)

    def _set_busy(self, busy: bool) -> None:
        self._add_btn.setEnabled(not busy)
        self._deduct_btn.setEnabled(not busy)
        self._refresh_btn.setEnabled(not busy)
