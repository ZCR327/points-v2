"""概览视图（ARCHITECTURE §9.2 "DashboardView"）。

布局：4 个统计卡片 + 趋势图 + Top 10 排行榜。
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from points_v2.core.logging import get_logger
from points_v2.ui.widgets.chart_widget import ChartWidget
from points_v2.ui.widgets.error_dialog import show_error
from points_v2.ui.workers import ServiceWorker

__all__ = ["DashboardView"]


class _StatCard(QFrame):
    """单个统计卡片（标题 + 数值 + 副标题）。"""

    def __init__(
        self,
        title: str,
        value: str = "—",
        subtitle: str = "",
        accent: str = "#1abc9c",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame {{ background: #fff; border-left: 4px solid {accent};"
            f"  border-radius: 4px; }}"
        )
        self.setFixedHeight(100)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(2)

        self._title = QLabel(title)
        self._title.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        layout.addWidget(self._title)

        self._value = QLabel(value)
        value_font = QFont()
        value_font.setPointSize(22)
        value_font.setBold(True)
        self._value.setFont(value_font)
        self._value.setStyleSheet(f"color: {accent};")
        layout.addWidget(self._value)

        self._subtitle = QLabel(subtitle)
        self._subtitle.setStyleSheet("color: #95a5a6; font-size: 11px;")
        layout.addWidget(self._subtitle)

    def set_value(self, value: str, subtitle: str = "") -> None:
        self._value.setText(value)
        if subtitle:
            self._subtitle.setText(subtitle)


class DashboardView(QWidget):
    """概览仪表盘。"""

    def __init__(self, services: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._services = services
        self._log = get_logger("system")
        self._threadpool = services.threadpool  # type: ignore[attr-defined]
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        # 标题栏
        header = QHBoxLayout()
        title = QLabel("📊 概览")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        header.addWidget(title)
        header.addStretch(1)
        self._refresh_btn = QPushButton("🔄 刷新")
        self._refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self._refresh_btn)
        outer.addLayout(header)

        # 4 个统计卡片
        cards = QGridLayout()
        cards.setSpacing(12)
        self._card_users = _StatCard("用户总数", accent="#3498db")
        self._card_points = _StatCard("总积分", accent="#1abc9c")
        self._card_records = _StatCard("流水总数", accent="#9b59b6")
        self._card_max = _StatCard("最高余额", accent="#e67e22")
        cards.addWidget(self._card_users, 0, 0)
        cards.addWidget(self._card_points, 0, 1)
        cards.addWidget(self._card_records, 0, 2)
        cards.addWidget(self._card_max, 0, 3)
        outer.addLayout(cards)

        # 趋势图 + 排行榜
        body = QHBoxLayout()
        body.setSpacing(12)

        # 趋势图（最近 7 天积分增量）
        chart_box = QFrame()
        chart_box.setStyleSheet("QFrame { background: #fff; border-radius: 4px; }")
        chart_layout = QVBoxLayout(chart_box)
        chart_layout.setContentsMargins(12, 8, 12, 8)
        chart_title = QLabel("📈 最近 7 天积分增量")
        chart_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        chart_layout.addWidget(chart_title)
        self._chart = ChartWidget()
        chart_layout.addWidget(self._chart, 1)
        body.addWidget(chart_box, 2)

        # 排行榜 Top 10
        rank_box = QFrame()
        rank_box.setStyleSheet("QFrame { background: #fff; border-radius: 4px; }")
        rank_layout = QVBoxLayout(rank_box)
        rank_layout.setContentsMargins(12, 8, 12, 8)
        rank_title = QLabel("🏆 积分榜 Top 10")
        rank_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        rank_layout.addWidget(rank_title)
        self._ranking_table = QTableWidget(0, 4)
        self._ranking_table.setHorizontalHeaderLabels(["#", "用户", "显示名", "积分"])
        self._ranking_table.verticalHeader().setVisible(False)
        self._ranking_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._ranking_table.setSelectionMode(QTableWidget.NoSelection)
        self._ranking_table.setAlternatingRowColors(True)
        self._ranking_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._ranking_table.setStyleSheet(
            "QTableWidget { gridline-color: #ecf0f1; }"
            "QHeaderView::section { background: #ecf0f1; padding: 6px; border: 0; }"
        )
        rank_layout.addWidget(self._ranking_table, 1)
        body.addWidget(rank_box, 1)

        outer.addLayout(body, 1)

        # 状态标签
        self._status = QLabel("")
        self._status.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        outer.addWidget(self._status)

    # ------------------------------------------------------------------ 数据
    def refresh(self) -> None:
        """刷新所有数据：调多个 service（异步）。"""
        self._refresh_btn.setEnabled(False)
        self._status.setText("加载中…")

        # 1. 系统统计
        points_service = self._services.points_service
        worker = ServiceWorker(
            points_service.get_stats,
            on_result=self._on_stats,
            on_error=self._on_stats_error,
        )
        self._threadpool.start(worker)

        # 2. Top 10 排行
        worker2 = ServiceWorker(
            lambda: points_service.get_ranking(period="all", limit=10),
            on_result=self._on_ranking,
            on_error=self._on_ranking_error,
        )
        self._threadpool.start(worker2)

        # 3. 7 天趋势（聚合最近 7 天的积分增量）
        worker3 = ServiceWorker(
            self._compute_7day_trend,
            on_result=self._on_trend,
            on_error=self._on_trend_error,
        )
        self._threadpool.start(worker3)

    def _compute_7day_trend(self) -> tuple[list[str], list[int]]:
        """聚合最近 7 天每天的积分增量。"""
        points_service = self._services.points_service
        all_records = points_service._points_repo.all()  # type: ignore[attr-defined]
        today = _dt.datetime.now(tz=_dt.timezone.utc).date()
        # 准备 7 天的 bucket
        days = [today - _dt.timedelta(days=i) for i in range(6, -1, -1)]
        buckets: dict[str, int] = {d.isoformat(): 0 for d in days}
        days_set = set(days)
        for rec in all_records:
            d = rec.created_at.date()
            if d in days_set:
                buckets[d.isoformat()] += rec.amount
        return list(buckets.keys()), list(buckets.values())

    def _on_stats(self, stats: Any) -> None:
        self._card_users.set_value(str(stats.user_count), "活跃用户")
        self._card_points.set_value(str(stats.total_points), "累计发放")
        self._card_records.set_value(str(stats.record_count), "条流水")
        self._card_max.set_value(str(stats.max_balance), "单用户最高")
        self._refresh_btn.setEnabled(True)
        self._status.setText(f"更新于 {_dt.datetime.now().strftime('%H:%M:%S')}")

    def _on_stats_error(self, exc: Exception) -> None:
        self._refresh_btn.setEnabled(True)
        self._status.setText("统计加载失败")
        show_error(exc, title="加载统计失败", parent=self)

    def _on_ranking(self, ranking: list[Any]) -> None:
        self._ranking_table.setRowCount(len(ranking))
        for row, item in enumerate(ranking):
            rank_item = QTableWidgetItem(str(item.rank))
            rank_item.setTextAlignment(Qt.AlignCenter)
            self._ranking_table.setItem(row, 0, rank_item)
            self._ranking_table.setItem(row, 1, QTableWidgetItem(item.username))
            self._ranking_table.setItem(row, 2, QTableWidgetItem(item.display_name))
            pts_item = QTableWidgetItem(str(item.total_points))
            pts_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._ranking_table.setItem(row, 3, pts_item)

    def _on_ranking_error(self, exc: Exception) -> None:
        show_error(exc, title="加载排行榜失败", parent=self)

    def _on_trend(self, data: tuple[list[str], list[int]]) -> None:
        labels, values = data
        # 把 YYYY-MM-DD 缩短成 MM-DD
        short = [d[5:] for d in labels]
        self._chart.plot_line(
            short,
            values,
            title="每日积分增量",
            xlabel="日期",
            ylabel="积分",
            label="积分",
            color="#1abc9c",
        )

    def _on_trend_error(self, exc: Exception) -> None:
        # 趋势失败不阻塞主流程
        self._chart.clear()
        self._log.warning(f"趋势加载失败: {exc}")
