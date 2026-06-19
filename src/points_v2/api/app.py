"""FastAPI app factory (ARCHITECTURE §8).

设计要点
--------

- :func:`create_app` 工厂函数：可重复构造独立实例（测试隔离）
- 注册 4 个 router（``/api/auth``、``/api/users``、``/api/points``、``/api/admin``）
- 全局 ``/health`` 健康检查
- 自定义 exception handler：``PointsV2Error`` → JSON 错误响应
- CORS：从 ``api.cors_origins`` 配置读取；空列表则不安装 CORSMiddleware
- **不**在模块层构造全局 ``app = create_app()``——避免 import 时副作用
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from points_v2.api.app_state import ServiceBundle, build_default_services
from points_v2.api.deps import error_response_payload, status_for_error
from points_v2.api.routers import admin, auth, points, users
from points_v2.core import config
from points_v2.core.exceptions import PointsV2Error


def _read_cors_origins() -> list[str]:
    try:
        origins = config.get("api.cors_origins", [])
    except Exception:  # noqa: BLE001 - 配置未初始化时退默认
        origins = []
    if isinstance(origins, str):
        return [o.strip() for o in origins.split(",") if o.strip()]
    if isinstance(origins, Iterable):
        return [str(o) for o in origins]
    return []


def create_app(
    *,
    services: ServiceBundle | None = None,
    cors_origins: list[str] | None = None,
    title: str | None = None,
) -> FastAPI:
    """构造 FastAPI app。

    :param services: 自定义 service 集合（**测试用**）；``None`` 时构造默认。
    :param cors_origins: CORS 白名单；``None`` 时从 ``api.cors_origins`` 读取。
    :param title: 应用标题；``None`` 时从 ``app.name`` 读取。
    """
    bundle = services or build_default_services()

    try:
        app_title = title or config.get("app.name", "智能回收社 积分系统 v2")
    except Exception:  # noqa: BLE001
        app_title = title or "智能回收社 积分系统 v2"
    if not isinstance(app_title, str):
        app_title = str(app_title)

    app = FastAPI(
        title=app_title,
        version="0.1.0",
        description="智能回收社 积分系统 v2 — HTTP API",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ---------------- exception handlers ----------------
    @app.exception_handler(PointsV2Error)
    async def _handle_points_v2_error(_request: Request, exc: PointsV2Error) -> JSONResponse:
        payload = error_response_payload(exc)
        return JSONResponse(status_code=status_for_error(exc), content=payload)

    @app.exception_handler(ValueError)
    async def _handle_value_error(_request: Request, exc: ValueError) -> JSONResponse:
        # 业务层抛 ValueError（如"积分不能为负"）→ 400
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": str(exc),
                    "details": {},
                },
            },
        )

    # ---------------- CORS ----------------
    origins = cors_origins if cors_origins is not None else _read_cors_origins()
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # ---------------- routers ----------------
    api_prefix = "/api"
    app.include_router(auth.router, prefix=api_prefix)
    app.include_router(users.router, prefix=api_prefix)
    app.include_router(points.router, prefix=api_prefix)
    app.include_router(admin.router, prefix=api_prefix)

    # ---------------- 根路由 & 健康检查 ----------------
    @app.get("/", include_in_schema=False)
    async def _root() -> dict[str, Any]:
        return {
            "name": app_title,
            "version": "0.1.0",
            "docs": "/docs",
            "health": "/health",
        }

    @app.get("/health", tags=["system"])
    async def _health() -> dict[str, Any]:
        return {"status": "ok"}

    # 把 bundle 挂到 app.state（便于 lifespan / 中间件访问）
    app.state.services = bundle

    return app


# ---------------------------------------------------------------------------
# ``python -m points_v2.api`` 入口
# ---------------------------------------------------------------------------
def main() -> int:
    """uvicorn 启动入口。"""
    import uvicorn

    # 初始化 core（路径 + 配置 + 日志）
    from points_v2.core import paths

    paths.setup()
    try:
        from points_v2.core import config as _cfg

        _cfg.setup()
    except Exception:  # noqa: BLE001
        pass

    try:
        from points_v2.core import logging as _log

        _log.setup()
    except Exception:  # noqa: BLE001
        pass

    app = create_app()
    try:
        host = str(config.get("api.host", "127.0.0.1"))
        port = int(config.get("api.port", 8765))
    except Exception:  # noqa: BLE001
        host = "127.0.0.1"
        port = 8765
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


__all__ = ["create_app", "main"]
