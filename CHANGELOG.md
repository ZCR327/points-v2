# 变更日志

> 倒序排列（最新在最上面）。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

---

## [0.1.0] - 2026-06-17

首个稳定版。完整 5 层架构 + UI + 插件 + 迁移 + 打包。

### Added（新增）

#### Track 1: core + domain + data (`a389309`)
- `core/paths.py` — 项目根 / 数据 / 日志 / 备份目录常量 + 幂等 `setup()`
- `core/config.py` — YAML + 环境变量合并加载，dot-path 取值
- `core/logging.py` — loguru 分类日志（system / login / points / users / sensitive）
- `core/exceptions.py` — 自定义异常体系（`PointsV2Error` + 7 子类）
- `core/container.py` — 轻量 DI 容器（单例 registry）
- `domain/enums.py` — `UserRole` / `OperationType` / `NotificationLevel` / `AuditAction`
- `domain/user.py` — `User` / `UserCreate` / `UserUpdate` Pydantic v2 模型
- `domain/points.py` — `PointsRecord` / `PointsAdjustment` / `UserRanking`
- `domain/audit.py` — `AuditLog` / `AuditFilter`
- `domain/notification.py` — `Notification`
- `data/base.py` — `JsonRepository[T]` 泛型抽象基类（原子写 + RLock）
- `data/user_repo.py` / `points_repo.py` / `audit_repo.py` / `notification_repo.py`
- 60 个测试，覆盖率 93%

#### Track 2: services + api
- `utils/hashing.py` — bcrypt 包装
- `utils/time.py` — UTC `datetime.now(tz=...)`
- `utils/validators.py` — username / amount 校验
- `services/auth_service.py` — login / logout / verify_token / change_password
- `services/user_service.py` — CRUD / lock / unlock
- `services/points_service.py` — add / deduct / transfer / ranking / stats
- `services/audit_service.py` — log / query
- `services/notification_service.py` — create / list / mark_read / broadcast
- `api/app.py` — FastAPI 工厂 + exception handlers + CORS
- `api/app_state.py` — `ServiceBundle` + `build_default_services`
- `api/deps.py` — `get_current_user` / `require_admin` / `status_for_error`
- `api/schemas.py` — 请求/响应 Pydantic 模型
- `api/routers/auth.py` / `users.py` / `points.py` / `admin.py`
- 11 个 API 端到端测试

#### Track 3: ui (PySide6) + workers
- `ui/app.py` — `QApplication` 启动 + `--no-gui` / `--api` / `--version`
- `ui/main_window.py` — `QMainWindow`（顶部栏 + 侧边栏 + `QStackedWidget` + 状态栏 + 时钟）
- `ui/views/login_view.py` — 用户名/密码表单 → `auth_service.login`
- `ui/views/dashboard_view.py` — 4 个统计卡片 + 7 天趋势图 + Top 10 排行榜
- `ui/views/points_view.py` — 积分流水表 + 加/扣对话框
- `ui/views/user_view.py` — 用户列表 + 详情 + CRUD（admin）
- `ui/views/admin_view.py` — 审计日志 / 通知广播 / 系统设置 3 tab
- `ui/widgets/data_table.py` — `BaseTableModel` + `DataTableWidget`
- `ui/widgets/chart_widget.py` — matplotlib 嵌入 Qt
- `ui/widgets/error_dialog.py` — 统一错误弹窗
- `ui/workers.py` — `ServiceWorker(QRunnable)` 包装 service 调用
- `tests/ui/test_smoke.py` — offscreen 模式 smoke 测试

#### Track 4: plugins + migrations + packaging
- `plugins/base.py` — `Plugin` 抽象基类 + `PluginContext`
- `plugins/loader.py` — `importlib.metadata.entry_points` 加载
- `plugins/builtin/example.py` — 示范插件
- `migrations/from_v5_9.py` — CLI 工具（`--source / --target / --dry-run`）
- `pyproject.toml` — 入口点 `points_v2.plugins` 注册 example
- `pyproject.toml` — CLI 脚本 `points-v2` / `points-v2-api` / `points-v2-migrate`
- `scripts/seed_data.py` — 造测试数据
- `scripts/main.spec` / `api.spec` — PyInstaller 配置

#### 文档
- `README.md` — 重写（特性、状态徽章、快速开始、目录结构）
- `DEVELOPING.md` — 开发指南（环境、测试、CI、调试）
- `CHANGELOG.md` — 本文件
- `docs/ARCHITECTURE.md` — 已有，本版未改
- `docs/screenshots/.gitkeep` — 截图占位

### Changed
- `pyproject.toml` — 新增 `gui` extras（PySide6 + matplotlib）+ `packaging` extras（PyInstaller）
- `data/{users,points,audit,notifications,sessions}.json` 数据布局同 v5.9 JSON 模式（不重写）

### Fixed
- `.gitignore` 锚定 `/data/` `/logs/` 避免误匹配 `src/points_v2/data/`（见 AGENTS.md K1）

### Security
- 默认管理员密码 `admin123` —— **首次登录后必须修改**（README 显式提示）
- v5.9 迁移时为每个用户生成新的 bcrypt 随机密码，**写入 `migration_report.json`**，管理员需安全分发

---

## 历史里程碑

| 日期 | 提交 | 描述 |
|---|---|---|
| 2026-06-12 | `8db81dd` | Foundation：pyproject / gitignore / config yamls / smoke test |
| 2026-06-12 | `a389309` | Track 1: core + domain + data（22 文件 + 60 测试） |
| 2026-06-12 | (sibling) | Track 2: services + api（13 文件 + 11 测试） |
| 2026-06-17 | (this) | Track 3+4: ui + plugins + migrations + docs（30+ 文件） |

---

## 路线图

### 0.2.0（计划中）
- 通知详情 / 已读标记 UI
- 用户改密对话框
- 数据导出（CSV / Excel）
- 暗黑模式（QSS 主题切换）

### 0.3.0（计划中）
- SQLite 仓储（沿用 `JsonRepository` 协议）
- 完整插件示例：「积分商城插件」
- 国际化（i18n）框架

### 1.0.0（生产候选）
- 覆盖率 ≥ 90%
- 性能基准测试
- 端到端 E2E 测试
- 完整 API 文档（mkdocstrings）
