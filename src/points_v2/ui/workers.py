"""UI workers — 后台线程执行 service 调用，避免阻塞主线程。

设计要点
--------

- :class:`ServiceWorker` 是 :class:`QRunnable` 子类，把任意 ``callable`` 塞进
  :class:`QThreadPool`，完成后通过 signal 通知 UI
- :class:`WorkerSignals` 提供 4 个标准 signal：started / finished / result / error
- **不**直接持有 widget 引用；widget 通过连接 signal 自己决定怎么更新
- 错误用 :class:`Exception` 传递（统一用 :func:`widgets.error_dialog.show_error` 处理）
"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

__all__ = ["ServiceWorker", "WorkerSignals"]


class WorkerSignals(QObject):
    """worker 信号集合（QRunnable 不能直接定义 signal，要靠 QObject）。"""

    started = Signal()
    finished = Signal()
    result = Signal(object)
    error = Signal(object)  # Exception


class ServiceWorker(QRunnable):
    """在 QThreadPool 中执行 ``fn(*args, **kwargs)`` 的 worker。

    用法::

        pool = QThreadPool.globalInstance()
        worker = ServiceWorker(self._load_data, on_result=self._on_loaded)
        pool.start(worker)
    """

    def __init__(
        self,
        fn: Callable[..., Any],
        *args: Any,
        on_result: Callable[[Any], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
        on_finished: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.signals = WorkerSignals()
        if on_result is not None:
            self.signals.result.connect(on_result)
        if on_error is not None:
            self.signals.error.connect(on_error)
        if on_finished is not None:
            self.signals.finished.connect(on_finished)

    @Slot()
    def run(self) -> None:  # noqa: D401 - QRunnable 接口
        """线程入口：调 fn，捕获异常，通过 signal 上报。"""
        self.signals.started.emit()
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.signals.result.emit(result)
        except Exception as exc:  # noqa: BLE001 - 统一捕获
            # 附 stack trace 到异常对象
            exc._worker_traceback = traceback.format_exc()  # type: ignore[attr-defined]
            self.signals.error.emit(exc)
        finally:
            self.signals.finished.emit()
