# 智能回收社 积分系统 v2

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![PySide6](https://img.shields.io/badge/PySide6-%E2%89%A56.6-green)](https://doc.qt.io/qtforpython-6/)
[![FastAPI](https://img.shields.io/badge/FastAPI-%E2%89%A50.110-009688)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

> 企业级 Python 桌面应用骨架 —— 把 v5.9 单文件（12923 行 Tkinter + Flask）重写为 PySide6 + FastAPI + Repository + DI 的分层架构，作为"如果当年这样写就好了"的参照版。

🚧 **重构中** — 当前阶段：项目骨架（pyproject、配置、路径、冒烟测试）。功能模块待实施。

---

## 功能

- 登录 / 用户管理 / 角色权限（super_admin / admin / operator / user）
- 积分增减 / 转账 / 排行榜 / 历史
- 审计日志 / 通知系统
- HTTP API（远程管理，监听 `127.0.0.1:8765`）
- 数据迁移（从 v5.9 单文件版导入）
- PyInstaller 打包（可选）

## 技术栈

| 类别 | 选型 |
|---|---|
| GUI | PySide6 (Qt6) |
| API | FastAPI + uvicorn |
| 数据 | JSON 文件（Repository 模式） |
| 日志 | loguru |
| 配置 | PyYAML + env 覆盖 |
| 密码 | bcrypt |
| 测试 | pytest + pytest-cov |
| Lint / 类型 | ruff + mypy (strict) |
| CI | GitHub Actions |
| 打包 | PyInstaller |

详见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

---

## 🚀 快速开始

```bash
# 1. 克隆 / 进入项目目录
cd "积分系统-v2-pyside6"

# 2. 创建虚拟环境（推荐）
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 3. 安装依赖（含开发工具）
pip install -e ".[dev]"

# 4. 启动桌面 GUI
python -m points_v2

# 5. 启动 HTTP API（另一个终端）
python -m points_v2.api

# 6. 跑测试
pytest tests/test_smoke.py -v
```

> 注：当前为骨架阶段，模块尚未实现；启动 `python -m points_v2` 会调用尚未落地的 `core.config.setup()` 与 `ui.app.run()` —— 这是预期的。

## 📁 项目结构

```
积分系统-v2-pyside6/
├── pyproject.toml              # 依赖、工具配置、入口点
├── docs/ARCHITECTURE.md        # 架构设计（团队共享契约）
├── config/                     # 配置（default / development / production）
├── src/points_v2/              # 主包
│   ├── core/                   # 基础设施（config / logging / paths / DI / exceptions）
│   ├── domain/                 # Pydantic 领域模型
│   ├── data/                   # Repository 数据访问层
│   ├── services/               # 业务服务层
│   ├── api/                    # FastAPI HTTP API
│   ├── ui/                     # PySide6 桌面 UI
│   ├── plugins/                # 插件（entry_points）
│   ├── migrations/             # 数据迁移（v5.9 → v2）
│   └── utils/                  # 工具
├── tests/                      # pytest 测试
└── .github/workflows/ci.yml    # CI（lint + test）
```

## 📝 文档

- 架构设计：[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- 开发指南：待补充（`docs/DEVELOPING.md`）
- 变更日志：待补充（`CHANGELOG.md`）
- API 文档：启动 API 后访问 `http://127.0.0.1:8765/docs`

## 📄 许可

MIT
