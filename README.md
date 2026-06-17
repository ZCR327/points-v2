# 智能回收社 积分系统 v2

> 一个 PySide6 桌面端 + FastAPI HTTP API 的企业级 Python 桌面应用骨架。
> 学生项目 / 教学示范 / 中小型积分管理平台。

[![Python](https://img.shields.io/badge/python-3.10--3.13-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-72%20passed-brightgreen.svg)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-93%25-yellowgreen.svg)](tests/)
[![Code style](https://img.shields.io/badge/code%20style-ruff-black.svg)](https://docs.astral.sh/ruff/)

---

## 特性

- **桌面端（PySide6）** — 登录、概览、积分流水、用户管理、审计/通知广播、系统设置
- **HTTP API（FastAPI）** — 与桌面端共享 service 层，可远程管理
- **架构分层** — `core / domain / data / services / api / ui`，依赖方向严格自上而下
- **数据持久化** — JSON Repository 模式（原子写、RLock 守护），未来可平移 SQLite/PostgreSQL
- **DI 容器** — `core/container.py` 轻量 registry（无三方依赖）
- **分类日志** — `loguru` + 5 个分类（system / login / points / users / sensitive）
- **配置合并** — `default.yaml` → `{APP_ENV}.yaml` → `POINTS_V2_*` 环境变量
- **插件系统** — `importlib.metadata` entry_points，可热插拔
- **数据迁移** — 从 v5.9 散落 JSON 一键导入（带 dry-run 报告）
- **测试覆盖** — pytest + 单元/集成/API/UI smoke，**60+ 测试**，覆盖率达 93%
- **打包** — PyInstaller spec 已就绪（`scripts/main.spec` / `api.spec`）
- **CI** — GitHub Actions 已配 lint + test

---

## 状态徽章

| 项目 | 状态 |
|---|---|
| Foundation (pyproject / gitignore / config) | ✅ done |
| Track 1: core + domain + data | ✅ done |
| Track 2: services + api | ✅ done |
| Track 3: ui (PySide6) + workers | ✅ done |
| Track 4: plugins + migrations + packaging | ✅ done |

**当前版本**：`0.1.0`（2026-06-17）

---

## 快速开始

### 安装

```powershell
# 克隆仓库
git clone https://github.com/xiaomi/points-v2.git
cd points-v2

# 创建虚拟环境（推荐项目本地）
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 装运行时 + GUI + 打包依赖
pip install -e ".[gui,packaging]"

# 装开发依赖（可选）
pip install -e ".[dev]"
```

### 启动桌面端

```powershell
python -m points_v2                  # 默认启动 GUI
python -m points_v2 --no-gui         # 仅 sanity-import
python -m points_v2 --version        # 打印版本
```

### 启动 HTTP API

```powershell
python -m points_v2 --api            # 监听 127.0.0.1:8765（默认）
python -m points_v2-api              # 入口脚本（等价）
```

API 文档：[http://127.0.0.1:8765/docs](http://127.0.0.1:8765/docs)

### 命令行入口

```powershell
points-v2          # 等价于 python -m points_v2
points-v2-api      # 等价于 python -m points_v2.api
points-v2-migrate  # 数据迁移工具（v5.9 → v2）
```

---

## 目录结构

```
points-v2/
├── pyproject.toml              # 依赖、工具配置、入口点、插件
├── README.md                   # 本文件
├── ARCHITECTURE.md             # 详细架构（替代 doc/ARCHITECTURE.md）
├── DEVELOPING.md               # 开发指南
├── CHANGELOG.md                # 变更日志
├── .github/workflows/ci.yml    # GitHub Actions
│
├── config/                     # YAML 配置
│   ├── default.yaml
│   ├── development.yaml
│   └── production.yaml
│
├── src/points_v2/              # 主包
│   ├── core/                   # 基础设施（paths / config / logging / exceptions / container）
│   ├── domain/                 # Pydantic 领域模型（user / points / audit / notification / enums）
│   ├── data/                   # Repository 层（JsonRepository 泛型基类）
│   ├── services/               # 业务服务（auth / user / points / audit / notification）
│   ├── api/                    # FastAPI HTTP API（4 个 router + exception handlers）
│   ├── ui/                     # PySide6 桌面 UI（app / main_window / 5 views / 3 widgets / workers）
│   ├── plugins/                # 插件系统（base / loader / builtin）
│   ├── migrations/             # 数据迁移（from_v5_9）
│   ├── utils/                  # 工具（hashing / time / validators）
│   ├── __init__.py
│   └── __main__.py             # python -m points_v2 入口
│
├── tests/                      # pytest 测试（60+ 用例）
│   ├── core/
│   ├── domain/
│   ├── data/
│   ├── services/
│   ├── api/
│   └── ui/                     # UI smoke（offscreen 模式）
│
├── docs/                       # 文档
│   ├── ARCHITECTURE.md
│   ├── API.md
│   └── screenshots/
│
├── scripts/                    # 工具脚本
│   ├── run_dev.py              # 开发模式启动
│   ├── seed_data.py            # 造测试数据
│   ├── main.spec               # PyInstaller: 桌面端
│   └── api.spec                # PyInstaller: API 端
│
└── data/                       # 数据目录（运行时创建，git 忽略）
    ├── users.json
    ├── points.json
    ├── audit.json
    ├── notifications.json
    ├── sessions.json
    └── backups/
```

---

## 默认账号

首次运行会自动创建默认管理员：

- **用户名**：`admin`
- **密码**：`admin123`（**请尽快修改！**）

如果没有自动创建（空数据目录），用 CLI 创建：

```powershell
python scripts/seed_data.py
```

---

## 测试 / Lint

```powershell
# 全部测试
pytest

# 单目录
pytest tests/services -v
pytest tests/ui -v

# 覆盖率
pytest --cov=points_v2 --cov-report=term-missing

# Lint
ruff check src tests
ruff format --check src tests

# 类型检查
mypy src/points_v2
```

---

## 打包

```powershell
pyinstaller scripts/main.spec      # 桌面端
pyinstaller scripts/api.spec       # API 端
```

产物在 `dist/points-v2/` 和 `dist/points-v2-api/`。

---

## 文档

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — 架构设计（必读）
- [DEVELOPING.md](DEVELOPING.md) — 开发指南
- [CHANGELOG.md](CHANGELOG.md) — 变更日志

---

## 协议

MIT License

---

## 致谢

- 项目：智能回收社（学生项目）
- 协作：Mavis 多 agent 编排
- 灵感：「如果当年这样写就好了」
