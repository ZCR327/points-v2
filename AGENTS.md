# AGENTS.md — 智能回收社 积分系统 v2

> Worker 必读：本文档是 **ARCHITECTURE.md 的操作补充**。架构契约以 `docs/ARCHITECTURE.md` 为准；本文档只记录：硬性 gate、踩过的坑、可复用的项目级模式。
>
> 每次任务结束如有新教训，先更新本文档再写代码；commit message 形式：`docs(agents): <lesson>`。

---

## 1. 硬性 Gate（每个 PR / 任务必须通过）

| 工具 | 命令 | 通过条件 |
|---|---|---|
| pytest | `pytest tests/core tests/domain tests/data` | 全过；新代码必须带测试 |
| pytest (新代码) | `pytest --cov=points_v2.<你的层> tests/<你的层>` | 该层 **每个模块 ≥ 80%**（行覆盖率） |
| ruff | `ruff check src tests` | 0 错；CI 会拒绝 |
| mypy | `mypy src/points_v2` | 0 错（`strict = true`，不要 `# type: ignore` 逃避） |
| git | `git log --oneline` | 单个原子 commit，message 形如 `feat(<layer>): <summary>` |

完整命令模板见 `docs/ARCHITECTURE.md §12`。

---

## 2. 环境 / 依赖

- 项目根：`C:\Users\xiaomi\Desktop\智能回收社\积分系统-v2-pyside6`
- Python 3.10。**系统 `python` 不保证装齐所有 deps** —— 任务 brief 说"依赖已装齐"但实际不是
- 推荐创建项目本地 `.venv/` 并在 venv 中跑测试：
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
  .\.venv\Scripts\python.exe -m pytest tests/
  ```
- 缺包时 `pip install` 会触发 daemon permission gate；通过 `<permission-ask>` 块向用户申请，**不要静默 `--user`**
- 跑测试 / lint 全部用 `.venv\Scripts\python.exe -m <tool>` 前缀，**不要** 用 `python -m <tool>`（会落到没装的系统 Python）

---

## 3. 项目专属模式（已实施，请沿用）

### 3.1 `JsonRepository[T]` 模式（data 层）

所有持久化对象走 `JsonRepository[T]` 泛型基类，文件位置 `data/<name>.json`：

- 子类只需覆盖 `_FILENAME` 和 `_pk(obj)`
- 提供 `load/save/insert/update/upsert/delete/get/find/find_one/all/count/clear/reload`
- 原子写：`tmp + os.replace`（同卷下 POSIX/Win 都是原子的）
- 锁：`threading.RLock` 守护所有读/写
- 文件错误统一抛 `StorageError`（带 `details` dict）

**新增实体的标准做法**（参考 `data/user_repo.py`）：
1. `src/points_v2/domain/<entity>.py` 定义 Pydantic 模型（`extra="forbid"`、UTC `datetime`、自动生成 `id`）
2. `src/points_v2/data/<entity>_repo.py` 继承 `JsonRepository[<Entity>]`，定义 `_FILENAME` / `_pk` / 业务查询方法
3. `src/points_v2/data/__init__.py` re-export
4. 测试覆盖：insert / get / update / delete + **2 个错误路径**（损坏 JSON、缺字段、并发、原子写）才能把覆盖率推到 80%+

### 3.2 配置加载顺序（core/config.py）

`default.yaml` → `{APP_ENV}.yaml` → `POINTS_V2_*` 环境变量（最高优先级，分隔符 `__`）。

- **测试**用 `tmp_config_dir` fixture 重定向 `paths.CONFIG_DIR` 到 `tmp_path/config/`，并 `config._config = None` 清除缓存
- 环境变量自动类型转换：`true`/`false` → bool；纯数字 → int；带小数 → float；其余 → str
- `get_config()` 总是返回 **深拷贝**，调用方修改不影响缓存

### 3.3 日志（core/logging.py）

- `setup()` 多次安全（先 `logger.remove()` 重建 sink）
- 分类：`system` / `login` / `points` / `users` / `sensitive`，通过 `get_logger(category)` 拿
- 非法 category 自动落到 `system`，不抛错
- 文件 sink 是 JSON（`serialize=True`），便于后续 ELK

### 3.4 测试约定

- `tests/conftest.py` 提供 `tmp_data_dir` / `tmp_config_dir` / `reset_config` / `fresh_container` 四个 fixture
- 任何需要 JSON 文件读写的测试**必须**用 `tmp_data_dir`，**严禁**依赖 `points_v2/core/paths.py` 的真实 `DATA_DIR`
- `pyproject.toml` 有 `filterwarnings = ["error", ...]` —— 任何 deprecation warning 都会让测试 fail；导入三方库时若确定是上游问题，显式 `filterwarnings(ignore::DeprecationWarning, ...)` 而**不是** `pytest.ini` 改全局
- 覆盖率要求每个模块 **≥ 80%**；很难达到 80% 的层（如 data/base.py）需写**防御性测试**——损坏 JSON、记录字段类型错误、`_FILENAME` 未定义等

---

## 4. 已踩的坑（**绝对不要重犯**）

| # | 坑 | 正确做法 |
|---|---|---|
| K1 | `.gitignore` 写 `data/` 会误匹配 `src/points_v2/data/` 等源码目录 | 锚定到根目录：`/data/`、`/logs/` |
| K2 | Pydantic v2 + 泛型 `T = TypeVar("T", bound=BaseModel)` 的 `Generic[T]` 子类，mypy 能识别 `obj.id` / `self._items`，**不要** 加 `# type: ignore[attr-defined]`（会产生 unused-ignore 警告） | 直接用属性访问，让 mypy 推断 |
| K3 | `sim110`（for + return → any()）、`sim105`（try-except-pass → suppress）、`sim114`（连续 if-pass 分支）会被 ruff 拒绝 | 重写为推荐形式 |
| K4 | 测试中 `set PYTHONPATH=src && pytest ...` 在 PowerShell 不需要（pyproject.toml 已配 `pythonpath = ["src"]`） | 直接 `.venv\Scripts\python.exe -m pytest` |
| K5 | Windows PowerShell `ls a b c` 会被 `Get-ChildItem` 拒绝（多 positional 参数不支持） | `Get-ChildItem a; Get-ChildItem b` 分开调用 |
| K6 | `from __future__ import annotations` + mypy + 泛型，会让 `T` 推断不准 → 导致冗余 `# type: ignore` | 避免在 Generic 类里加 `type: ignore`；先尝试 `obj.id`（直接属性） |

---

## 5. 模块依赖方向（强制）

```
core  ←  domain  ←  data  ←  services  ←  api  ←  ui
                                                  ←  plugins
```

- 上层可以 `from points_v2.<下层> import ...`
- **下层绝不 import 上层**（这是架构硬约束，ARCHITECTURE §4.1 写明）
- 跨层协调走 `core/container.py` 的 `Container`（DI）

---

## 6. 已完成 Track（截至 2026-06-12）

- [x] **Foundation** (`8db81dd`) — pyproject、gitignore、config yamls、smoke test
- [x] **Track 1: core + domain + data** (`a389309`) — 本次任务
  - 15 个源文件 + 9 个测试文件 + 60 个测试
  - 覆盖率 93%、ruff 0 错、mypy 0 错
- [ ] Track 2: services + api + 集成测试（进行中）
- [ ] Track 3: ui (PySide6) + workers
- [ ] Track 4: plugins + migrations + packaging

后续 track 接手时**先看本文档 §3 和 §4**，再读 ARCHITECTURE.md 对应章节。

---

## 7. 变更日志

| 日期 | 任务 | 文档变更 |
|---|---|---|
| 2026-06-12 | Track 1 完成 | 初始化 AGENTS.md；记录 K1-K6 坑、JsonRepository 模式、测试约定 |
