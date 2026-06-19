"""QTableView + QAbstractTableModel 基类（ARCHITECTURE §9）。

设计要点
--------

- :class:`BaseTableModel` 实现：column header / row count / column count / data / headerData
- 子类只需定义 :attr:`COLUMNS`（``list[tuple[label, attr]]``）和实现 :meth:`_row_data`
- :class:`DataTableWidget` 包装 ``QTableView``，固定一些常用属性（不可编辑 / 隔行变色 / 选择行）
- **不**支持排序 / 过滤 —— 学生项目够用；后续需要再扩展
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHeaderView, QTableView, QVBoxLayout, QWidget

__all__ = ["BaseTableModel", "DataTableWidget"]


class BaseTableModel(QAbstractTableModel):
    """通用 ``QAbstractTableModel`` 基类。

    子类用法::

        class UserTableModel(BaseTableModel):
            COLUMNS = [("用户名", "username"), ("积分", "points"), ("角色", "role")]

            def _row_data(self, row_index: int) -> User:
                return self._items[row_index]

            def _cell(self, row_index: int, attr: str) -> str:
                obj = self._row_data(row_index)
                val = getattr(obj, attr, "")
                if hasattr(val, "value"):  # Enum
                    return str(val.value)
                return str(val)
    """

    COLUMNS: Sequence[tuple[str, str]] = []  # [(显示名, 属性名), ...]

    def __init__(self, items: list[Any] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: list[Any] = list(items) if items else []

    # ------------------------------------------------------------------ 公共
    def set_items(self, items: list[Any]) -> None:
        """重置数据并通知视图刷新。"""
        self.beginResetModel()
        self._items = list(items)
        self.endResetModel()

    def append_items(self, items: list[Any]) -> None:
        """追加数据（一次 begin/end 包装，避免 N 次刷新）。"""
        if not items:
            return
        start = len(self._items)
        self.beginInsertRows(QModelIndex(), start, start + len(items) - 1)
        self._items.extend(items)
        self.endInsertRows()

    def clear(self) -> None:
        self.set_items([])

    def items(self) -> list[Any]:
        return list(self._items)

    # ------------------------------------------------------------------ 必须实现
    def _row_data(self, row_index: int) -> Any:
        raise NotImplementedError

    def _cell(self, row_index: int, attr: str) -> Any:
        """默认实现：``getattr(obj, attr)``，可被子类覆盖（如格式化日期）。"""
        obj = self._row_data(row_index)
        val = getattr(obj, attr, "")
        if hasattr(val, "value"):  # Enum → 取 value
            return val.value
        return val

    # ------------------------------------------------------------------ Qt 接口
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        if parent.isValid():
            return 0
        return len(self._items)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        if parent.isValid():
            return 0
        return len(self.COLUMNS)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        if role == Qt.DisplayRole:
            _, attr = self.COLUMNS[index.column()]
            return self._cell(index.row(), attr)
        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignLeft | Qt.AlignVCenter)
        if role == Qt.ForegroundRole:
            # 偶数行浅灰前景，增加可读性
            if index.row() % 2 == 1:
                return QColor("#555")
            return None
        return None

    def headerData(  # noqa: N802 (Qt parent uses camelCase)
        self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole
    ) -> Any:  # noqa: N802
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal and 0 <= section < len(self.COLUMNS):
            return self.COLUMNS[section][0]
        if orientation == Qt.Vertical:
            return str(section + 1)
        return None


# ---------------------------------------------------------------------------
# 简单行模型适配器：直接传 list[tuple]，col 走 lambda
# ---------------------------------------------------------------------------
class RowListModel(BaseTableModel):
    """接受 ``list[tuple]`` + formatter 的轻量模型。"""

    def __init__(
        self,
        rows: list[tuple[Any, ...]] | None = None,
        *,
        columns: Sequence[tuple[str, str]] | None = None,
        formatters: Sequence[Callable[[Any], Any]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        if columns is None:
            columns = []
        self.COLUMNS = columns
        self._formatters = list(formatters) if formatters else []
        super().__init__(list(rows) if rows else [], parent)

    def _row_data(self, row_index: int) -> tuple[Any, ...]:
        return self._items[row_index]

    def _cell(self, row_index: int, attr: str) -> Any:
        # 找到 attr 在 COLUMNS 中的索引
        for i, (_, a) in enumerate(self.COLUMNS):
            if a == attr:
                val = self._items[row_index][i]
                if i < len(self._formatters) and self._formatters[i] is not None:
                    return self._formatters[i](val)
                return val
        return None


# ---------------------------------------------------------------------------
# DataTableWidget：包装 QTableView
# ---------------------------------------------------------------------------
class DataTableWidget(QWidget):
    """通用数据表 widget。

    用法::

        model = UserTableModel()
        view = DataTableWidget(model=model)
        view.set_items([...])
    """

    def __init__(
        self,
        *,
        model: BaseTableModel | None = None,
        stretch_last: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._table = QTableView()
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.setSelectionMode(QTableView.SingleSelection)
        self._table.setEditTriggers(QTableView.NoEditTriggers)
        self._table.setSortingEnabled(False)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(stretch_last)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self._table.setStyleSheet(
            "QTableView {"
            "  background: #fafafa; alternate-background-color: #f0f0f0;"
            "  gridline-color: #dcdcdc; selection-background-color: #1abc9c;"
            "  selection-color: white;"
            "}"
            "QHeaderView::section { background: #ecf0f1; padding: 6px;"
            "  border: 0; border-right: 1px solid #dcdcdc; font-weight: bold; }"
        )
        if model is not None:
            self._table.setModel(model)
        layout.addWidget(self._table)

    @property
    def table(self) -> QTableView:
        return self._table

    def setModel(self, model: BaseTableModel) -> None:  # noqa: N802 - Qt 命名
        self._model = model
        self._table.setModel(model)

    def model(self) -> BaseTableModel | None:
        return self._model

    def set_items(self, items: list[Any]) -> None:
        if self._model is None:
            return
        self._model.set_items(items)

    def selected_row_index(self) -> int:
        idx = self._table.currentIndex()
        if not idx.isValid():
            return -1
        return idx.row()
