"""matplotlib 嵌入 Qt 容器（ARCHITECTURE §9.2 "DashboardView 趋势图"）。

设计要点
--------

- :class:`ChartWidget` 包装 :class:`FigureCanvasQTAgg`（matplotlib 官方 Qt backend）
- 提供 :meth:`plot_line` / :meth:`plot_bar` / :meth:`clear` 三个常用接口
- **不**存业务数据 —— 数据由调用方（dashboard_view）准备
- matplotlib 与 PySide6 的 EventLoop 通过 ``FigureCanvas`` 自动桥接
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtWidgets import QVBoxLayout, QWidget

__all__ = ["ChartWidget"]


class ChartWidget(QWidget):
    """通用 matplotlib 图表 widget。"""

    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._figure = Figure(figsize=(5, 3), dpi=100)
        self._figure.patch.set_facecolor("#fafafa")
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._canvas.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)
        # 默认占一个 axes
        self._ax = self._figure.add_subplot(111)
        self._configure_axes(self._ax)

    @property
    def figure(self) -> Figure:
        return self._figure

    @property
    def canvas(self) -> FigureCanvasQTAgg:
        return self._canvas

    def clear(self) -> None:
        """清空图表内容（保留坐标系）。"""
        self._ax.clear()
        self._configure_axes(self._ax)
        self._canvas.draw_idle()

    def plot_line(
        self,
        x: Sequence[Any],
        y: Sequence[float],
        *,
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
        label: str = "",
        color: str = "#1abc9c",
        marker: str = "o",
    ) -> None:
        """画折线图。"""
        self._ax.clear()
        self._configure_axes(self._ax)
        self._ax.plot(list(x), list(y), marker=marker, color=color, label=label or "趋势")
        if title:
            self._ax.set_title(title)
        if xlabel:
            self._ax.set_xlabel(xlabel)
        if ylabel:
            self._ax.set_ylabel(ylabel)
        if label:
            self._ax.legend(loc="best", fontsize=9)
        self._figure.tight_layout()
        self._canvas.draw_idle()

    def plot_bar(
        self,
        labels: Sequence[str],
        values: Sequence[float],
        *,
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
        color: str = "#3498db",
    ) -> None:
        """画柱状图（横轴为字符串标签）。"""
        self._ax.clear()
        self._configure_axes(self._ax)
        self._ax.bar(list(labels), list(values), color=color)
        if title:
            self._ax.set_title(title)
        if xlabel:
            self._ax.set_xlabel(xlabel)
        if ylabel:
            self._ax.set_ylabel(ylabel)
        self._figure.tight_layout()
        self._canvas.draw_idle()

    @staticmethod
    def _configure_axes(ax: Any) -> None:
        """统一坐标轴样式。"""
        ax.set_facecolor("#fafafa")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#bdc3c7")
        ax.spines["bottom"].set_color("#bdc3c7")
        ax.tick_params(colors="#555", labelsize=9)
        ax.grid(True, alpha=0.3, linestyle="--", linewidth=0.5)
