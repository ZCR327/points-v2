# 开发指南

> 面向参与本项目开发的同学 / 协作者。
> 目标读者：能熟练使用 git + Python，想贡献代码或跑通项目。

---

## 1. 环境准备

### 1.1 系统要求

| 工具 | 版本 | 备注 |
|---|---|---|
| Python | 3.10 - 3.13 | 推荐 3.12 |
| Git | 2.30+ | 推送 / 拉取 |
| pip | 24+ | 旧版不支持 PEP 660 |
| OS | Windows 10+ / macOS 12+ / Linux | 跨平台 |

### 1.2 推荐的 IDE

- **PyCharm**（用户偏好）— 配置好 `.venv` 即可
- VS Code — 推荐装 Python + Pylance + Ruff 扩展

### 1.3 创建虚拟环境

```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 1.4 安装依赖

```powershell
# 完整开发环境（含 GUI + 打包 + 测试工具）
pip install -e ".[gui,packaging,dev]"

# 如果只开发非 GUI 模块
pip install -e ".[dev]"
```

---

## 2. 项目布局

```
src/points_v2/
├── core/         # 不依赖任何上层的"基础设施"
├── domain/       # Pydantic 模型；不依赖 core 之外的
├── data/         # 持久化；只依赖 domain
├── services/     # 业务编排；只依赖 data + core
├── api/          # FastAPI；依赖 services
├── ui/           # PySide6；依赖 services（不依赖 api）
├── plugins/      # 插件；依赖 core，可注入 services
├── migrations/   # 一次性脚本
└── utils/        # 通用工具
```

**依赖方向严格自上而下**（见 `AGENTS.md §5`）。

---

## 3. 跑测试

### 3.1 基本

```powershell
# 全部
pytest

# 单文件 / 单目录
pytest tests/services/test_auth_service.py
pytest tests/api

# 按关键字
pytest -k "test_login"
```

### 3.2 覆盖率

```powershell
pytest --cov=points_v2 --cov-report=term-missing
```

目标：每个模块 ≥ 80%。

### 3.3 标记

- `pytest -m "not slow"` — 跳过慢测试
- `pytest -m integration` — 仅集成测试

（目前未定义 marker，pyproject.toml 配置了 `--strict-markers`）

---

## 4. Lint / 格式化

```powershell
# 检查
ruff check src tests

# 自动修复
ruff check src tests --fix

# 格式化
ruff format src tests

# 仅检查格式
ruff format --check src tests
```

### 4.1 配置（pyproject.toml `[tool.ruff]`）

- line-length: 100
- select: E / W / F / I / B / UP / N / SIM / C4
- ignore: E501, B008（FastAPI Depends）

### 4.2 类型检查

```powershell
mypy src/points_v2
```

- `strict = true` — 不要轻易加 `# type: ignore`
- 已豁免 `PySide6.*` / `loguru`（无 type stub）

---

## 5. 运行

### 5.1 桌面端

```powershell
python -m points_v2
```

- 首次启动：自动创建 `data/` `logs/` 目录
- 默认管理员：`admin / admin123`（**记得改**）
- 关闭时清理后台线程（最多等 2 秒）

### 5.2 API 端

```powershell
python -m points_v2 --api          # 用 uvicorn 启动
python -m points_v2-api            # 同上
```

访问 [http://127.0.0.1:8765/docs](http://127.0.0.1:8765/docs) 看 OpenAPI UI。

### 5.3 开发模式（API + GUI 同时）

```powershell
python scripts/run_dev.py
```

### 5.4 UI smoke（CI 用）

```powershell
$env:QT_QPA_PLATFORM="offscreen"
python -c "from points_v2.ui.app import create_qt_app; from points_v2.ui.main_window import MainWindow; app=create_qt_app(); w=MainWindow(); w.show(); app.processEvents(); print('UI started OK')"
```

---

## 6. 添加新功能

### 6.1 新增领域模型

1. `src/points_v2/domain/<entity>.py` 定义 Pydantic `BaseModel`（`extra="forbid"`、UTC `datetime`、自动 `id`）
2. `src/points_v2/data/<entity>_repo.py` 继承 `JsonRepository[<Entity>]`
3. `src/points_v2/data/__init__.py` re-export
4. `tests/domain/test_<entity>.py` + `tests/data/test_<entity>_repo.py`
5. **覆盖率 ≥ 80%** 才能 commit

### 6.2 新增 service

1. `src/points_v2/services/<entity>_service.py` 接收 `Repository` 作依赖
2. **不**直接 import 其他 service —— 走 `core/container.py`
3. `src/points_v2/services/__init__.py` re-export
4. `tests/services/test_<entity>_service.py`

### 6.3 新增 API 端点

1. `src/points_v2/api/schemas.py` 加 Pydantic `BaseModel`（请求 / 响应）
2. `src/points_v2/api/routers/<feature>.py` 加 router
3. `src/points_v2/api/app.py` `include_router(...)`
4. `src/points_v2/api/deps.py` 注入 `get_current_user` / `require_admin`
5. `tests/api/test_<feature>.py` 至少 1 happy + 1 error path

### 6.4 新增 UI 视图

1. `src/points_v2/ui/views/<feature>_view.py` 继承 `QWidget`
2. `src/points_v2/ui/main_window.py` 注册到 `_inner_stack`
3. 所有 service 调用走 :class:`points_v2.ui.workers.ServiceWorker`（不阻塞主线程）
4. 错误统一走 :func:`points_v2.ui.widgets.error_dialog.show_error`
5. `tests/ui/test_smoke.py` 加 1 个测试

### 6.5 新增插件

1. 实现 :class:`points_v2.plugins.base.Plugin` 子类
2. 在你的 `pyproject.toml` 注册：

   ```toml
   [project.entry-points."points_v2.plugins"]
   myplugin = "my_pkg.module:MyPlugin"
   ```

3. 安装：`pip install -e .`（自动发现）
4. 验证：`python -c "from points_v2.plugins.loader import load_plugins; print(load_plugins())"`

---

## 7. 数据迁移

```powershell
# dry-run（不写文件）
python -m points_v2.migrations.from_v5_9 --source "C:\path\to\v5.9\data" --target "C:\path\to\v2\data" --dry-run

# 实际迁移
python -m points_v2.migrations.from_v5_9 --source "C:\path\to\v5.9\data" --target "C:\path\to\v2\data"
```

报告写到 `<target>/migration_report.json`，包含：
- 用户 / 流水统计
- 临时新密码（用户首次登录后需改）
- username → 新 id 映射
- 错误 / 警告列表

**注意事项**：
- v5.9 密码用 SHA256+salt，v2 用 bcrypt —— **所有导入用户密码会重置**
- v5.9 流水时间戳格式混杂，已做兼容
- 中文 username 不被 v2 接受（v2 用 `^[A-Za-z0-9_.-]+$`）—— 会被 skip

---

## 8. 打包

```powershell
# 桌面端
pyinstaller scripts/main.spec

# API 端
pyinstaller scripts/api.spec
```

产物：`dist/points-v2/` / `dist/points-v2-api/`

**已知问题**：
- PyInstaller + PySide6 在 Windows 上可能需要 `--collect-all PySide6`
- macOS 上需要 `--target-architecture universal2`（可选）

---

## 9. CI / CD

`.github/workflows/ci.yml` 跑：
- Lint：`ruff check src tests`
- Format：`ruff format --check src tests`
- Type：`mypy src/points_v2`
- Test：`pytest --cov=points_v2 --cov-report=xml`

matrix: Python 3.10 / 3.11 / 3.12 / 3.13

**PR 前本地全部跑一遍**：

```powershell
ruff check src tests
ruff format --check src tests
mypy src/points_v2
pytest --cov=points_v2
```

---

## 10. 常见问题

### Q1: `pip install -e ".[gui]"` 失败

pip < 24 不支持 PEP 660 editable 装纯 `pyproject.toml` 项目。先升级：

```powershell
python -m pip install --upgrade pip
```

### Q2: PySide6 启动报 "no Qt platform plugin"

设置 `QT_QPA_PLATFORM=offscreen`（CI）或安装系统 Qt 依赖（Linux）。

### Q3: `pytest` 报 `ModuleNotFoundError: No module named 'points_v2'`

确保 `pyproject.toml` 里 `pythonpath = ["src"]` 存在（已在）；或手动：

```powershell
$env:PYTHONPATH = "src"
pytest
```

### Q4: ruff 报 `B008` 在 FastAPI 的 `Depends`

已在 `[tool.ruff.lint]` 加 `ignore = ["B008"]`，无影响。

### Q5: mypy 报 unused ignore

如果你加了 `# type: ignore[xxx]` 但 mypy 没用上 —— 删掉。详见 `AGENTS.md` K2 / K6。

### Q6: 数据迁移中文 username 被跳过

v2 的 `User.username` 限制 `^[A-Za-z0-9_.-]+$`（避免编码问题）。中文用户需：
1. 在迁移报告里查 `errors`
2. 手动改 username（v2 Pydantic 校验）
3. 或扩展 `domain/user.py` 的 `_USERNAME_RE`（**不推荐**）

---

## 11. 调试技巧

### 11.1 打印配置

```python
from points_v2.core import config
config.setup()
import json; print(json.dumps(config.get_config(), indent=2, ensure_ascii=False))
```

### 11.2 临时换数据目录

```python
import points_v2.core.paths as paths
paths.DATA_DIR = paths.Path("/tmp/points-v2-test")
```

### 11.3 看线程池

```python
from PySide6.QtCore import QThreadPool
print(QThreadPool.globalInstance().activeThreadCount())
```

### 11.4 让 pytest 输出多

```powershell
pytest -v -s --tb=long
```

---

## 12. 协作流程

1. **建分支**：`git checkout -b feat/<short-name>`
2. **改代码**（小步 commit）
3. **跑测试 + lint**：确保全过
4. **commit message**：`feat(<layer>): <summary>` / `fix(<layer>): <summary>` / `docs: <summary>`
5. **PR** —— 描述清楚改了什么、为什么、怎么测
6. **CI 通过后** —— reviewer 同意才 merge

---

## 13. 项目文化

- **KISS**：能简单就别复杂
- **类型注解**：所有公共 API 必须有类型
- **测试**：新代码必须带测试
- **文档**：改完代码改文档
- **依赖方向**：上层 → 下层（绝不反向）
- **失败明确**：抛有意义的异常，不静默

---

## 14. 资源

- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [PySide6 文档](https://doc.qt.io/qtforpython-6/)
- [Pydantic v2 文档](https://docs.pydantic.dev/latest/)
- [loguru 文档](https://loguru.readthedocs.io/)
- [PyInstaller 文档](https://pyinstaller.org/en/stable/)
- [项目架构设计](docs/ARCHITECTURE.md)
- [变更日志](CHANGELOG.md)
- [AGENTS.md](AGENTS.md) — 踩过的坑
