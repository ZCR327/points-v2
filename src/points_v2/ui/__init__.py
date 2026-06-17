"""PySide6 desktop UI for 智能回收社 积分系统 v2 (ARCHITECTURE §9).

依赖方向：``core`` + ``domain`` + ``data`` + ``services`` ← ``ui``
（UI 不依赖 api；UI 与 API 共享 service 层）。

设计要点
--------

- 所有耗时 service 调用走 :class:`points_v2.ui.workers.ServiceWorker`
  （``QRunnable`` + ``QThreadPool``），主线程不阻塞
- 错误统一走 :class:`points_v2.ui.widgets.error_dialog.show_error`
- 入口 :func:`points_v2.ui.app.run` 由 :mod:`points_v2.__main__` 调用
- 启动模式：默认 GUI；``--no-gui`` 跳过（仅导入，用于测试/纯命令行场景）
"""

from __future__ import annotations

__all__: list[str] = []
