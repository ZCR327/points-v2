# 积分系统 v2 — 架构设计文档

> **作者**：项目组（协作：Mavis）
> **生成日期**：2026-06-12
> **状态**：设计阶段（团队实施前必读）
> **目标读者**：所有参与实施的 worker（coder / tester / verifier）

---

## 1. 项目目标

把现有 v5.9 单文件（12923 行 Tkinter + Flask）重写为**企业级 Python 桌面应用骨架**，**专业够用**，作为"如果当年这样写就好了"的参照版。

**功能对齐 v5.9**：登录、用户管理、积分增减、积分排行、审计日志、通知、HTTP API（远程管理）

**架构升级**：
- GUI：Tkinter → **PySide6 (Qt6)**
- API：Flask → **FastAPI**（异步、自动 OpenAPI）
- 配置：散落常量 → **YAML/TOML 集中 + env 覆盖**
- 日志：print + 散落 log → **loguru 分类日志**
- 数据：直接 json.dump → **Repository 抽象**
- 错误：try/except print → **自定义异常 + 统一错误对话框**
- 测试：1 个文件 → **pytest + 5-10 示范测试**
- 打包：手动 → **PyInstaller spec**
- CI：无 → **GitHub Actions**（lint + test）

---

## 2. 技术栈选型（已与用户确认）

| 类别 | 选型 | 版本要求 | 理由 |
|---|---|---|---|
| Python | 3.10+（推荐 3.12） | >=3.10,<3.14 | 类型注解 + match-case |
| GUI | **PySide6** | >=6.6 | Qt 官方 LGPL、跨平台 |
| API | **FastAPI** | >=0.110 | 异步、自动 OpenAPI |
| ASGI 服务器 | uvicorn | >=0.27 | FastAPI 标配 |
| 数据校验 | Pydantic | >=2.5 | FastAPI 标配 |
| 持久化 | JSON 文件（同 v5.9） | - | 简化、零依赖 |
| 日志 | loguru | >=0.7 | 比标准库好用 |
| 配置 | PyYAML | >=6.0 | 人类可读 |
| 测试 | pytest | >=8.0 | 标配 |
| 覆盖率 | pytest-cov | >=4.1 | 标配 |
| Lint | ruff | >=0.1 | 速度快，替代 flake8+black+isort |
| 类型检查 | mypy | >=1.7 | 严格模式 |
| HTTP 客户端（测试） | httpx | >=0.27 | FastAPI 测试用 |
| 打包 | PyInstaller | >=6.0 | 学生作品加分 |
| CI | GitHub Actions | - | 免费、主流 |

---

## 3. 目录结构

```
积分系统-v2-pyside6/
├── pyproject.toml              # 依赖、工具配置、入口点
├── README.md                    # 项目介绍
├── ARCHITECTURE.md              # 本文档
├── DEVELOPING.md                # 开发指南（如何跑、如何测试）
├── CHANGELOG.md                 # 变更日志
├── .gitignore                   # Python + 项目特定
├── .github/
│   └── workflows/
│       └── ci.yml               # GitHub Actions：lint + test
├── .vscode/                     # 编辑器配置（可选，git 忽略）
│
├── config/                      # 配置文件（YAML）
│   ├── default.yaml             # 默认配置
│   ├── development.yaml         # 开发环境覆盖
│   └── production.yaml          # 生产环境覆盖
│
├── src/
│   └── points_v2/               # 主包
│       ├── __init__.py          # 版本号
│       ├── __main__.py          # python -m points_v2 入口
│       │
│       ├── core/                # 基础设施层
│       │   ├── __init__.py
│       │   ├── config.py        # 配置加载（YAML + env）
│       │   ├── logging.py       # loguru 配置（分类日志）
│       │   ├── exceptions.py    # 自定义异常体系
│       │   ├── container.py     # 轻量 DI 容器（单例）
│       │   └── paths.py         # 路径常量 + 初始化
│       │
│       ├── domain/              # 领域层（Pydantic models）
│       │   ├── __init__.py
│       │   ├── enums.py         # UserRole / OperationType / etc.
│       │   ├── user.py          # User / UserCreate / UserUpdate
│       │   ├── points.py        # PointsRecord / PointsAdjustment
│       │   ├── audit.py         # AuditLog
│       │   └── notification.py  # Notification
│       │
│       ├── data/                # 数据访问层（Repository 模式）
│       │   ├── __init__.py
│       │   ├── base.py          # JsonRepository 抽象基类
│       │   ├── user_repo.py     # UserRepository
│       │   ├── points_repo.py   # PointsRepository
│       │   ├── audit_repo.py    # AuditRepository
│       │   └── notification_repo.py
│       │
│       ├── services/            # 业务服务层
│       │   ├── __init__.py
│       │   ├── auth_service.py  # 认证（密码哈希、token、登录）
│       │   ├── user_service.py  # 用户管理（CRUD）
│       │   ├── points_service.py# 积分（增减、排行、统计）
│       │   ├── audit_service.py # 审计（操作日志）
│       │   └── notification_service.py
│       │
│       ├── api/                 # FastAPI HTTP API
│       │   ├── __init__.py
│       │   ├── app.py           # FastAPI app 工厂
│       │   ├── deps.py          # 依赖注入（get_current_user 等）
│       │   ├── routers/
│       │   │   ├── __init__.py
│       │   │   ├── auth.py      # /api/auth/login, /me
│       │   │   ├── users.py     # /api/users CRUD
│       │   │   ├── points.py    # /api/points 加减
│       │   │   └── admin.py     # /api/admin/* 远程管理
│       │   └── schemas.py       # API 请求/响应 schema
│       │
│       ├── ui/                  # PySide6 桌面 UI
│       │   ├── __init__.py
│       │   ├── app.py           # QApplication 启动
│       │   ├── main_window.py   # 主窗口
│       │   ├── views/
│       │   │   ├── __init__.py
│       │   │   ├── login_view.py
│       │   │   ├── dashboard_view.py
│       │   │   ├── points_view.py
│       │   │   ├── admin_view.py
│       │   │   └── user_view.py
│       │   ├── widgets/
│       │   │   ├── __init__.py
│       │   │   ├── data_table.py    # 通用数据表
│       │   │   ├── chart_widget.py  # matplotlib 嵌入 Qt
│       │   │   └── error_dialog.py  # 统一错误弹窗
│       │   └── workers.py       # 后台线程（QThread）— 不阻塞 UI
│       │
│       ├── plugins/             # 插件（entry_points 加载）
│       │   ├── __init__.py
│       │   ├── base.py          # Plugin 抽象基类
│       │   └── builtin/
│       │       ├── __init__.py
│       │       └── example.py   # 一个示范插件
│       │
│       ├── migrations/          # 数据迁移
│       │   ├── __init__.py
│       │   └── from_v5_9.py     # 从 v5.9 JSON 导入的脚本
│       │
│       └── utils/               # 工具
│           ├── __init__.py
│           ├── hashing.py       # 密码哈希
│           ├── time.py          # 时间格式化
│           └── validators.py    # 通用验证函数
│
├── tests/                       # pytest 测试
│   ├── conftest.py              # fixtures
│   ├── core/                    # 配置 / 日志 / 异常 / 容器测试
│   ├── domain/                  # 模型验证测试
│   ├── services/                # 业务逻辑测试
│   ├── api/                     # API 端到端测试
│   └── ui/                      # UI 启动 smoke test
│
├── docs/                        # 文档
│   ├── ARCHITECTURE.md          # 本文件
│   ├── API.md                   # 自动生成的 OpenAPI 文档链接
│   └── screenshots/             # UI 截图
│
└── scripts/                     # 工具脚本
    ├── migrate_from_v5_9.py     # 迁移入口
    ├── seed_data.py             # 造测试数据
    └── run_dev.sh               # 开发模式启动
```

**总文件数（含配置）**：~50 个（30 个 src + 5-10 个 test + 5 个 config + 5 个 doc + 5 个 ci/script）

---

## 4. 架构模式

### 4.1 层次（自下而上）

```
┌─────────────────────────────────────────────────────────┐
│  ui/ (PySide6)            api/ (FastAPI)                │  ← 入口层
├─────────────────────────────────────────────────────────┤
│  services/    (业务编排、跨实体操作)                       │  ← 服务层
├─────────────────────────────────────────────────────────┤
│  data/        (Repository 模式、数据访问)                 │  ← 数据访问层
├─────────────────────────────────────────────────────────┤
│  domain/      (Pydantic models、领域规则)                 │  ← 领域层
├─────────────────────────────────────────────────────────┤
│  core/        (config / logging / exceptions / DI)      │  ← 基础设施
└─────────────────────────────────────────────────────────┘
```

**依赖方向**：上层 → 下层（绝不反向）

### 4.2 关键模式

#### Repository 模式（数据层）
- `JsonRepository[T]` 抽象基类：`load() / save() / find() / find_one() / insert() / update() / delete()`
- 子类：`UserRepository` / `PointsRepository` / 等
- **好处**：将来换 SQLite / PostgreSQL，service / api / ui 都不用改

#### Service 层（业务编排）
- 每个 service 持有对应 repository
- 业务规则在这里：扣积分要校验余额、转账要事务、低积分要触发通知
- **不直接调其他 service**（避免循环依赖）—— 用事件或 `Container` 协调

#### 轻量 DI 容器（core/container.py）
- 单例 registry：`container.register("user_service", lambda: UserService(...))`
- 解析：`container.resolve("user_service")`
- 作用：替换 + 测试时注入 mock

#### 自定义异常（core/exceptions.py）
```python
class PointsV2Error(Exception): pass
class AuthError(PointsV2Error): pass
class InvalidCredentialsError(AuthError): pass
class InsufficientPointsError(PointsV2Error): pass
class UserNotFoundError(PointsV2Error): pass
class DuplicateUserError(PointsV2Error): pass
# ...
```

#### 统一错误处理
- API 层：FastAPI exception handler → JSON 错误响应
- UI 层：`error_dialog.py` → 中文 QMessageBox
- 日志层：loguru 记录堆栈

### 4.3 并发模型

- **UI 层**：所有耗时操作走 `QThread` / `QThreadPool`，主线程不阻塞
- **API 层**：FastAPI 异步（async def 路由）
- **数据层**：文件 IO 是同步的，但用 `asyncio.to_thread` 包装

### 4.4 配置加载顺序

```
1. config/default.yaml          ← 基础默认值
2. config/{ENV}.yaml            ← 环境覆盖（ENV 来自 APP_ENV，默认 development）
3. 环境变量                     ← 最高优先级（PREFIX_POINTS_V2_）
```

---

## 5. 数据模型（domain 层）

### User
```python
class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    OPERATOR = "operator"
    USER = "user"

class User(BaseModel):
    id: str                    # UUID
    username: str              # 唯一
    display_name: str
    role: UserRole             # 默认 USER
    points: int                # 当前积分余额
    password_hash: str         # bcrypt
    is_active: bool            # 默认 True
    is_locked: bool            # 登录锁定
    failed_login_count: int    # 默认 0
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None
```

### PointsRecord
```python
class OperationType(str, Enum):
    EARN = "earn"            # 回收获得
    SPEND = "spend"          # 商城消费
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    ADJUST = "adjust"        # 管理员调整
    REFUND = "refund"

class PointsRecord(BaseModel):
    id: str
    user_id: str
    operation: OperationType
    amount: int               # 正数
    balance_after: int        # 记录时的余额（审计用）
    reason: str               # 文本
    operator_id: str | None   # 谁操作的（系统/管理员）
    created_at: datetime
```

### AuditLog
```python
class AuditLog(BaseModel):
    id: str
    user_id: str | None       # 谁触发的
    action: str               # "user.create" / "points.add" / etc.
    resource: str | None      # 影响的资源 ID
    details: dict             # 任意上下文
    ip_address: str | None
    created_at: datetime
```

### Notification
```python
class NotificationLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

class Notification(BaseModel):
    id: str
    user_id: str | None       # None = 全员
    level: NotificationLevel
    title: str
    content: str
    is_read: bool
    created_at: datetime
```

---

## 6. 数据存储（data 层）

### 6.1 文件布局
```
data/
├── users.json
├── points.json              # 积分流水
├── audit.json
├── notifications.json
├── sessions.json            # API token（仅 API 用）
├── settings.json
├── products.json            # 积分商城商品
└── backups/                 # 每日自动备份
    └── 2026-06-12_030000.json
```

### 6.2 JsonRepository 行为
- 启动时**从磁盘加载全部**到内存（数据量小）
- 每次写入**先写临时文件 → rename**（原子写，防崩溃损坏）
- 每 5 分钟 / 每次关键操作后 flush 一次
- **大文件（>10MB）不适用**——但学生项目不会到那个量

### 6.3 锁
- 单进程内：threading.RLock
- 跨进程：fcntl.flock（Windows 退化到 msvcrt）
- **学生项目单进程使用**，所以弱锁即可

### 6.4 迁移
- `migrations/from_v5_9.py` 提供 CLI：
  ```bash
  python -m points_v2.migrations.from_v5_9 --source <v5.9_数据目录> --target <v2_数据目录>
  ```
- 读取 v5.9 的 `data/marks.json` / `data/users.json` / `data/audit_log.json` 等
- 字段映射 → 写入 v2 的 JSON 文件
- **幂等**：可重复跑（用 ID 去重）

---

## 7. 服务层 API（services/）

### AuthService
```python
class AuthService:
    def login(username: str, password: str) -> AuthToken
    def logout(token: str) -> None
    def verify_token(token: str) -> User
    def change_password(user_id: str, old: str, new: str) -> None
```

### UserService
```python
class UserService:
    def create(user: UserCreate) -> User
    def get_by_id(user_id: str) -> User
    def get_by_username(username: str) -> User
    def list(offset: int, limit: int) -> list[User]
    def update(user_id: str, update: UserUpdate) -> User
    def delete(user_id: str) -> None
    def lock(user_id: str, reason: str) -> None
    def unlock(user_id: str) -> None
```

### PointsService
```python
class PointsService:
    def add(user_id: str, amount: int, reason: str, operator_id: str) -> PointsRecord
    def deduct(user_id: str, amount: int, reason: str, operator_id: str) -> PointsRecord
    def transfer(from_id: str, to_id: str, amount: int, operator_id: str) -> tuple[PointsRecord, PointsRecord]
    def get_history(user_id: str, days: int) -> list[PointsRecord]
    def get_ranking(period: Literal["week", "month", "all"]) -> list[UserRanking]
    def get_stats() -> SystemStats
```

### AuditService
```python
class AuditService:
    def log(action: str, user_id: str | None, resource: str | None, details: dict) -> AuditLog
    def query(filters: AuditFilter) -> list[AuditLog]
    def get_user_actions(user_id: str, days: int) -> list[AuditLog]
```

### NotificationService
```python
class NotificationService:
    def create(level: NotificationLevel, title: str, content: str, user_id: str | None) -> Notification
    def list_for_user(user_id: str, include_global: bool) -> list[Notification]
    def mark_read(notification_id: str) -> None
    def broadcast(level: NotificationLevel, title: str, content: str) -> None
```

---

## 8. API 设计（api/）

### 8.1 端点
```
POST   /api/auth/login              # 登录拿 token
POST   /api/auth/logout             # 登出
GET    /api/auth/me                 # 当前用户信息

GET    /api/users                   # 列出用户
POST   /api/users                   # 创建用户（admin）
GET    /api/users/{id}              # 查用户
PUT    /api/users/{id}              # 改用户
DELETE /api/users/{id}              # 删用户（admin）

GET    /api/users/{id}/points       # 查积分余额
GET    /api/users/{id}/points/history  # 积分历史
POST   /api/points/add              # 加积分
POST   /api/points/deduct           # 扣积分
POST   /api/points/transfer         # 转账

GET    /api/rankings                # 排行榜
GET    /api/stats                   # 系统统计

GET    /api/audit                   # 审计查询（admin）
GET    /api/notifications           # 我的通知
POST   /api/notifications/{id}/read # 标记已读

GET    /health                      # 健康检查
GET    /docs                        # 自动 OpenAPI UI
```

### 8.2 认证
- Bearer token（JWT 简化版 — 不用第三方库，自己实现 HS256）
- 或简单 random token + `data/sessions.json` 映射（学生项目够用）
- 选 **方案 B**（更简单、无 JWT 依赖）

### 8.3 错误响应
```json
{
  "error": {
    "code": "INSUFFICIENT_POINTS",
    "message": "积分不足",
    "details": { "balance": 10, "required": 50 }
  }
}
```

---

## 9. UI 设计（ui/）

### 9.1 主窗口布局
```
┌────────────────────────────────────────────────────────┐
│  智能回收社 积分系统 v2              [👤 admin] [退出]  │  ← 顶部栏
├──────────┬─────────────────────────────────────────────┤
│  📊 概览  │                                             │
│  💰 积分  │           主内容区（QStackedWidget）        │
│  👥 用户  │                                             │
│  📋 审计  │                                             │
│  🔔 通知  │                                             │
│  ⚙️ 设置  │                                             │
└──────────┴─────────────────────────────────────────────┘
```

### 9.2 视图
- **LoginView**：用户名/密码 → 登录 → 进主窗口
- **DashboardView**：4 个统计卡片 + 趋势图（matplotlib）+ 排行榜 Top 10
- **PointsView**：积分流水表 + 加减积分按钮
- **UserView**：用户列表（搜索/筛选）+ 详情
- **AdminView**：审计日志、通知广播、系统设置
- **SettingsView**：改密码、API 配置、关于

### 9.3 后台线程
- 所有 service 调用走 `QThreadPool` + `QRunnable`
- 完成后 emit signal 更新 UI
- 错误统一走 `error_dialog.py`

### 9.4 样式
- 用 Qt 默认主题 + 简单 QSS（不写花哨样式）
- 中文字体：系统默认（macOS 苹方 / Windows 微软雅黑 / Linux 文泉驿）

---

## 10. 配置示例（config/default.yaml）

```yaml
app:
  name: "智能回收社 积分系统"
  version: "2.0.0"
  env: development
  debug: true

paths:
  data_dir: "data"
  log_dir: "logs"
  backup_dir: "data/backups"

logging:
  level: INFO
  rotation: "10 MB"
  retention: "30 days"
  console: true

database:
  type: json  # 未来可换 sqlite
  backup_interval_minutes: 30

api:
  host: "127.0.0.1"
  port: 8765
  cors_origins: []

security:
  password_min_length: 8
  max_failed_logins: 5
  lock_duration_minutes: 15
  session_ttl_hours: 24

points:
  min_balance_warning: 10
  max_transfer_per_day: 10000

ui:
  theme: default
  language: zh_CN
```

---

## 11. 测试策略

### 11.1 测试金字塔
```
       /\
      /E2E\         ← tests/api/ + tests/ui/ 启动 smoke（少量）
     /─────\
    /集成测试 \      ← tests/services/（中量）
   /──────────\
  /   单元测试   \   ← tests/domain/ + tests/core/（大量）
 /────────────────\
```

### 11.2 覆盖率目标
- 单元测试：domain + utils **100%**
- 集成测试：services **80%+**
- API 测试：所有端点 **1 happy path + 1 error path**
- UI 测试：仅启动 smoke（Qt 测试框架 QTest 太重，跳过）

### 11.3 测试数据
- `tests/conftest.py` 提供 fixtures：
  - `tmp_data_dir` — 每次测试用临时数据目录
  - `sample_user` — 一个测试用户
  - `admin_user` — 一个管理员
  - `user_service` — 预填数据的 service 实例

---

## 12. 开发流程

### 12.1 本地启动
```bash
# 装依赖
pip install -e ".[dev]"

# 启动桌面
python -m points_v2

# 启动 API
python -m points_v2.api

# 两个一起（开发模式）
python scripts/run_dev.py
```

### 12.2 测试
```bash
pytest                          # 全部
pytest tests/core               # 单目录
pytest -k test_login            # 按名字
pytest --cov=points_v2          # 覆盖率
```

### 12.3 Lint
```bash
ruff check src tests            # lint
ruff format src tests           # 格式化
mypy src                        # 类型检查
```

### 12.4 打包
```bash
pyinstaller scripts/main.spec   # 桌面端
pyinstaller scripts/api.spec    # API 端
```

---

## 13. CI（.github/workflows/ci.yml）

```yaml
name: CI
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -e ".[dev]"
      - run: ruff check src tests
      - run: ruff format --check src tests
      - run: mypy src
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix: { python-version: ["3.10", "3.11", "3.12"] }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: ${{ matrix.python-version }} }
      - run: pip install -e ".[dev]"
      - run: pytest --cov=points_v2 --cov-report=xml
```

---

## 14. 风险与回滚

| 风险 | 缓解 |
|---|---|
| 30 文件体量大、写不完 | 拆成 3 平行 track + integration gate |
| worker 之间接口不一致 | 共享本设计文档 + container.py 早定 |
| 依赖装不上（PySide6 在 Windows 上偶尔有坑）| CI 在 ubuntu-latest 跑，Windows 用户自行验证 |
| 数据迁移丢数据 | 提供 dry-run + 详细日志 + 不删源数据 |
| 30 分钟超时 | 大任务 25-30 分钟上限；拆分够细 |

---

## 15. 不做的事

- ❌ 不做 HDMI 大屏模式（v5.9 那个 v6.0 分支）
- ❌ 不做云备份 / 2FA / 数据同步（enhancements/ 里那些）—— 这些是 v3+ 的事
- ❌ 不做 DDD 完整模式 / CQRS / 事件溯源（学生项目 overkill）
- ❌ 不做完整的 i18n 框架（只支持中文，UI 文字不抽 t()）
- ❌ 不做 docker 镜像（学生项目本地跑就行）

---

## 16. 完成定义（Definition of Done）

- [ ] 所有 worker 任务 ACCEPT
- [ ] `pip install -e ".[dev]"` 在 Windows + macOS + Linux 都成功
- [ ] `python -m points_v2` 启动 GUI 无报错
- [ ] `python -m points_v2.api` 启动 API 监听 8765
- [ ] `pytest --cov` 跑通，覆盖率 ≥ 60%
- [ ] `ruff check` + `mypy` 0 错
- [ ] README + ARCHITECTURE + DEVELOPING 三个文档齐全
- [ ] 迁移脚本 dry-run + 实际迁移 v5.9 数据成功
- [ ] GitHub Actions 跑通（push 到 GitHub 之后）
- [ ] PyInstaller 打包出可执行文件（可选）

---

**这是所有 worker 必读的共享契约。** 实施时如果发现需要偏离，先更新本文件再改代码。
