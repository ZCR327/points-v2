"""用户管理视图（ARCHITECTURE §9.2 "UserView"）。

布局：用户列表 + 详情面板 + CRUD（仅 admin/operator 可见增删按钮）。
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from points_v2.core.logging import get_logger
from points_v2.domain.enums import UserRole
from points_v2.domain.user import User, UserCreate, UserUpdate
from points_v2.ui.widgets.error_dialog import ask_confirm, show_error, show_info
from points_v2.ui.workers import ServiceWorker

__all__ = ["UserView"]


class _CreateUserDialog(QDialog):
    """创建用户对话框。"""

    def __init__(
        self,
        *,
        default_role: UserRole = UserRole.USER,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("新建用户")
        self.setMinimumWidth(360)
        layout = QFormLayout(self)

        self._username = QLineEdit()
        self._username.setMaxLength(32)
        layout.addRow("用户名:", self._username)

        self._display_name = QLineEdit()
        self._display_name.setMaxLength(64)
        layout.addRow("显示名:", self._display_name)

        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.Password)
        self._password.setMaxLength(128)
        layout.addRow("密码:", self._password)

        self._role = QLineEdit(default_role.value)
        self._role.setReadOnly(True)
        layout.addRow("角色:", self._role)

        self._points = QSpinBox()
        self._points.setRange(0, 1_000_000_000)
        self._points.setValue(0)
        layout.addRow("初始积分:", self._points)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _validate_and_accept(self) -> None:
        if not self._username.text().strip():
            QMessageBox.warning(self, "提示", "用户名不能为空")
            return
        if not self._display_name.text().strip():
            QMessageBox.warning(self, "提示", "显示名不能为空")
            return
        if len(self._password.text()) < 8:
            QMessageBox.warning(self, "提示", "密码至少 8 位")
            return
        self.accept()

    def data(self) -> UserCreate:
        return UserCreate(
            username=self._username.text().strip(),
            display_name=self._display_name.text().strip(),
            password=self._password.text(),
            role=UserRole(self._role.text()),
            initial_points=self._points.value(),
        )


class UserView(QWidget):
    """用户列表 + CRUD。"""

    def __init__(self, services: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._services = services
        self._log = get_logger("users")
        self._threadpool = services.threadpool  # type: ignore[attr-defined]
        self._current_user: User | None = None
        self._users: list[User] = []
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        # 左：用户列表
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("👥 用户列表")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        header.addWidget(title)
        header.addStretch(1)
        self._refresh_btn = QPushButton("🔄")
        self._refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self._refresh_btn)
        self._new_btn = QPushButton("➕ 新建")
        self._new_btn.clicked.connect(self._on_create)
        header.addWidget(self._new_btn)
        left_layout.addLayout(header)

        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍 搜索用户名/显示名…")
        self._search.textChanged.connect(self._on_search)
        left_layout.addWidget(self._search)

        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_select)
        self._list.setStyleSheet(
            "QListWidget { background: #fff; border: 1px solid #ecf0f1; }"
            "QListWidget::item { padding: 8px; }"
            "QListWidget::item:selected { background: #1abc9c; color: white; }"
        )
        left_layout.addWidget(self._list, 1)
        left.setFixedWidth(320)
        outer.addWidget(left)

        # 右：详情
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self._detail_title = QLabel("选择一个用户查看详情")
        self._detail_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        right_layout.addWidget(self._detail_title)

        self._detail = QLabel("（无）")
        self._detail.setWordWrap(True)
        self._detail.setStyleSheet(
            "QLabel { background: #fff; padding: 16px; border: 1px solid #ecf0f1;"
            "  border-radius: 4px; }"
        )
        self._detail.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        right_layout.addWidget(self._detail, 1)

        # 操作按钮
        action_row = QHBoxLayout()
        self._edit_btn = QPushButton("✏️ 编辑")
        self._edit_btn.clicked.connect(self._on_edit)
        self._edit_btn.setEnabled(False)
        action_row.addWidget(self._edit_btn)
        self._lock_btn = QPushButton("🔒 锁定")
        self._lock_btn.clicked.connect(self._on_lock)
        self._lock_btn.setEnabled(False)
        action_row.addWidget(self._lock_btn)
        self._unlock_btn = QPushButton("🔓 解锁")
        self._unlock_btn.clicked.connect(self._on_unlock)
        self._unlock_btn.setEnabled(False)
        action_row.addWidget(self._unlock_btn)
        self._delete_btn = QPushButton("🗑 删除")
        self._delete_btn.clicked.connect(self._on_delete)
        self._delete_btn.setEnabled(False)
        action_row.addWidget(self._delete_btn)
        action_row.addStretch(1)
        right_layout.addLayout(action_row)

        outer.addWidget(right, 1)

    # ------------------------------------------------------------------ 数据
    def set_current_user(self, user: User) -> None:
        self._current_user = user
        self.refresh()

    def refresh(self) -> None:
        self._refresh_btn.setEnabled(False)
        user_service = self._services.user_service
        worker = ServiceWorker(
            lambda: user_service.list(offset=0, limit=500),
            on_result=self._on_users_loaded,
            on_error=self._on_users_error,
        )
        self._threadpool.start(worker)

    def _on_users_loaded(self, users: list[User]) -> None:
        self._users = users
        self._render_list(users)
        self._refresh_btn.setEnabled(True)

    def _on_users_error(self, exc: Exception) -> None:
        self._refresh_btn.setEnabled(True)
        show_error(exc, title="加载用户失败", parent=self)

    def _render_list(self, users: list[User]) -> None:
        keyword = self._search.text().strip().lower()
        self._list.clear()
        for u in users:
            if keyword and keyword not in u.username.lower() and keyword not in u.display_name.lower():
                continue
            label = f"{u.display_name}（{u.username}）\n   {u.role.value} · {u.points} 分"
            if u.is_locked:
                label += " · 🔒"
            if not u.is_active:
                label += " · ⛔"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, u.id)
            self._list.addItem(item)

    def _on_search(self, _text: str) -> None:
        self._render_list(self._users)

    def _on_select(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            self._detail_title.setText("选择一个用户查看详情")
            self._detail.setText("（无）")
            self._edit_btn.setEnabled(False)
            self._lock_btn.setEnabled(False)
            self._unlock_btn.setEnabled(False)
            self._delete_btn.setEnabled(False)
            return
        user_id = current.data(Qt.UserRole)
        user = next((u for u in self._users if u.id == user_id), None)
        if user is None:
            return
        self._render_detail(user)

    def _render_detail(self, user: User) -> None:
        self._detail_title.setText(f"{user.display_name}（{user.username}）")
        status_bits = []
        status_bits.append("✓ 活跃" if user.is_active else "⛔ 已停用")
        status_bits.append("🔒 锁定" if user.is_locked else "✓ 正常")
        status_bits.append(f"角色: {user.role.value}")
        created = user.created_at.strftime("%Y-%m-%d %H:%M:%S")
        last_login = (
            user.last_login_at.strftime("%Y-%m-%d %H:%M:%S")
            if user.last_login_at
            else "从未登录"
        )
        self._detail.setText(
            f"<b>ID:</b> {user.id}<br/>"
            f"<b>显示名:</b> {user.display_name}<br/>"
            f"<b>用户名:</b> {user.username}<br/>"
            f"<b>角色:</b> {user.role.value}<br/>"
            f"<b>积分:</b> {user.points}<br/>"
            f"<b>状态:</b> {' / '.join(status_bits)}<br/>"
            f"<b>创建时间:</b> {created}<br/>"
            f"<b>上次登录:</b> {last_login}<br/>"
            f"<b>登录失败次数:</b> {user.failed_login_count}"
        )
        is_admin = self._is_admin()
        self._edit_btn.setEnabled(is_admin)
        self._lock_btn.setEnabled(is_admin and not user.is_locked)
        self._unlock_btn.setEnabled(is_admin and user.is_locked)
        self._delete_btn.setEnabled(is_admin and user.id != (self._current_user.id if self._current_user else None))

    def _is_admin(self) -> bool:
        if self._current_user is None:
            return False
        return self._current_user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)

    # ------------------------------------------------------------------ 操作
    def _on_create(self) -> None:
        if not self._is_admin():
            show_info("只有管理员可以创建用户", parent=self)
            return
        dlg = _CreateUserDialog(parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.data()
        user_service = self._services.user_service
        worker = ServiceWorker(
            lambda: user_service.create(data),
            on_result=lambda u: self._on_action_done(f"创建用户 {u.username} 成功"),
            on_error=self._on_action_error,
        )
        self._threadpool.start(worker)

    def _on_edit(self) -> None:
        user = self._selected_user()
        if user is None:
            return
        if not self._is_admin():
            show_info("只有管理员可以编辑用户", parent=self)
            return
        # 简化：只让修改 display_name 和 points
        new_name, ok = QInputDialog.getText(
            self, "编辑显示名", "新的显示名:", text=user.display_name
        )
        if not ok:
            return
        new_points, ok = QInputDialog.getInt(
            self, "编辑积分", "新的积分余额:", value=user.points, minValue=0, maxValue=1_000_000_000
        )
        if not ok:
            return
        user_service = self._services.user_service
        patch = UserUpdate(display_name=new_name, points=new_points)
        worker = ServiceWorker(
            lambda: user_service.update(user.id, patch),
            on_result=lambda u: self._on_action_done(f"更新用户 {u.username} 成功"),
            on_error=self._on_action_error,
        )
        self._threadpool.start(worker)

    def _on_lock(self) -> None:
        user = self._selected_user()
        if user is None:
            return
        if not ask_confirm(f"确定锁定用户 {user.username}？", parent=self):
            return
        user_service = self._services.user_service
        worker = ServiceWorker(
            lambda: user_service.lock(user.id, reason="管理员锁定"),
            on_result=lambda u: self._on_action_done(f"已锁定 {u.username}"),
            on_error=self._on_action_error,
        )
        self._threadpool.start(worker)

    def _on_unlock(self) -> None:
        user = self._selected_user()
        if user is None:
            return
        user_service = self._services.user_service
        worker = ServiceWorker(
            lambda: user_service.unlock(user.id),
            on_result=lambda u: self._on_action_done(f"已解锁 {u.username}"),
            on_error=self._on_action_error,
        )
        self._threadpool.start(worker)

    def _on_delete(self) -> None:
        user = self._selected_user()
        if user is None:
            return
        if not ask_confirm(
            f"确定删除用户 {user.username}？此操作不可恢复！",
            parent=self,
            default_yes=False,
        ):
            return
        user_service = self._services.user_service
        worker = ServiceWorker(
            lambda: user_service.delete(user.id),
            on_result=lambda _: self._on_action_done(f"已删除 {user.username}"),
            on_error=self._on_action_error,
        )
        self._threadpool.start(worker)

    def _selected_user(self) -> User | None:
        item = self._list.currentItem()
        if item is None:
            return None
        user_id = item.data(Qt.UserRole)
        return next((u for u in self._users if u.id == user_id), None)

    def _on_action_done(self, message: str) -> None:
        show_info(message, parent=self)
        self.refresh()

    def _on_action_error(self, exc: Exception) -> None:
        show_error(exc, title="操作失败", parent=self)
