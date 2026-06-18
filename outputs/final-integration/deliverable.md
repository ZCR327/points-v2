# Deliverable — final-integration

## Summary

verifier 跑完了 6 项集成 gate：依赖安装、107/107 测试 PASS（覆盖率 64% ≥ 60%）、`ruff check` 0 错（owner ruff --fix + 我修的 SIM102）、E2E 业务流 12/12 PASS、既有 API 套件 11/11 PASS。Mypy 103 错为 pre-existing（PySide6 第三方类型不完整 + fastapi/pydantic 推断缺口），按 owner 协调意见文档化分类未硬修。PyInstaller 试打包被环境层 Python 3.10.0 dis 模块 bug 阻塞，非项目代码问题。

## Changed files

### 项目内（verifier 写入或修改）

1. **`src/points_v2/api/routers/users.py`** — 修复 `SIM102`（line 111-121 nested if → and-merged if，与 `is_self and not is_admin` 合并）
2. **`.mavis/plans/plan.yaml`** — owner ruff --fix 期间改动（已在 working tree）

### 工作区（verifier 写入；待 owner 决定是否移到目标位置）

3. **`C:\Users\xiaomi\.mavis\sessions\mvs_2265ed1afca148e0ae268eb085f4d51f\workspace\e2e_smoke.py`** — 12 步 E2E 业务流脚本（任务 brief 要求 `scripts/e2e_smoke.py`，因 workspace 边界外文件写入被 permission 拦阻，落在此处）
4. **`C:\Users\xiaomi\.mavis\sessions\mvs_2265ed1afca148e0ae268eb085f4d51f\workspace\final_integration_report.md`** — 最终集成报告（任务 brief 要求 `reports/final_integration_report.md`，同上原因落在此处）
5. **`C:\Users\xiaomi\.mavis\sessions\mvs_2265ed1afca148e0ae268eb085f4d51f\workspace\deliverable.md`** — 本文件

### 仓库 working tree（owner ruff --fix 已改 + verifier SIM102 + PyInstaller 残留）

- `src/points_v2/api/__init__.py`（owner ruff --fix）
- `src/points_v2/api/app_state.py`（owner ruff --fix）
- `src/points_v2/api/deps.py`（owner ruff --fix）
- `src/points_v2/api/routers/admin.py`（owner ruff --fix）
- `src/points_v2/api/routers/points.py`（owner ruff --fix）
- `src/points_v2/api/routers/users.py`（owner ruff --fix + verifier SIM102 fix）
- `src/points_v2/services/auth_service.py`（owner ruff --fix）
- `tests/services/test_auth_service.py`（owner ruff --fix）
- `tests/services/test_user_audit_notification.py`（owner ruff --fix）
- `points-v2.spec`、`points-v2-api.spec`、`build/points-v2/`（PyInstaller 失败留下的残留，需 `mavis-trash` 清理）

## Notes for verifier / owner

### 关键证据

| Gate | 命令 | 结果 |
|---|---|---|
| 测试 + 覆盖率 | `pytest --cov=points_v2 --cov-report=term-missing tests/` | **107/107 PASS, 64%** |
| ruff | `ruff check src tests` | **All checks passed!** |
| mypy | `mypy src/points_v2` | **103 errors**（pre-existing，§3.2 分类） |
| E2E | `python <workspace>/e2e_smoke.py` | **12/12 PASS** |
| 既有 API 套件 | `pytest tests/api/test_endpoints.py -v` | **11/11 PASS** |
| PyInstaller | `pyinstaller --onefile --name points-v2 src/points_v2/__main__.py` | **IndexError: tuple index out of range**（Python 3.10.0 dis bug） |

### Permission 拦截说明

verifier 在尝试写以下文件时被 permission classifier 拦截（"writes outside workspace root"）：
- `scripts/e2e_smoke.py`（项目内）
- `reports/final_integration_report.md`（项目内）
- `outputs/final-integration/deliverable.md`（plan output 目录，亦被判定为 workspace 外）

为不阻塞报告交付，verifier 把三个文件落在 **agent workspace**：
- `C:\Users\xiaomi\.mavis\sessions\mvs_2265ed1afca148e0ae268eb085f4d51f\workspace\`

owner 如需把它们移到任务 brief 指定的最终位置（`scripts/e2e_smoke.py` / `reports/final_integration_report.md` / `outputs/final-integration/deliverable.md`），可直接 `Move-Item` 复制（已经过测试，runtime 行为已验证）。

### PyInstaller 环境修复

失败根因：系统 Python 是 **3.10.0**（2021-10-04 最早释出版本），其 `dis._get_const_info` 有已知 bug。
不需改项目代码，**任一即可**：

1. 升级 Python ≥ 3.10.12（推荐）
2. 降级 PyInstaller 至 5.13（最后一个稳定 3.10 兼容版）
3. 用 `python -m nuitka` 替代（额外依赖）

### 与任务 brief 的偏差

| 维度 | brief 期望 | 实际 | 性质 |
|---|---|---|---|
| audit log ≥ 4 条 | 业务层（add / deduct / transfer）也写审计 | 仅 auth_service 写审计 → 2 条 | product gap（ARCHITECTURE §7 未实现） |
| 通知自动触发 | transfer 自动给收款方发通知 | admin 显式创建 | product gap |
| PyInstaller | 成功 | 失败（环境 bug） | 环境问题 |

### Working tree 状态

```
$ git status
On branch master
Changes not staged for commit:
	modified:   .mavis/plans/plan.yaml
	modified:   src/points_v2/api/__init__.py
	modified:   src/points_v2/api/app_state.py
	modified:   src/points_v2/api/deps.py
	modified:   src/points_v2/api/routers/admin.py
	modified:   src/points_v2/api/routers/points.py
	modified:   src/points_v2/api/routers/users.py   ← verifier + owner 改动
	modified:   src/points_v2/services/auth_service.py
	modified:   tests/services/test_auth_service.py
	modified:   tests/services/test_user_audit_notification.py
Untracked:
	points-v2.spec         ← PyInstaller 残留
	points-v2-api.spec     ← PyInstaller 残留
	build/                 ← PyInstaller 残留
```

按 owner 协调意见，verifier 建议 commit 命令：

```powershell
git add src/points_v2/api/ src/points_v2/services/auth_service.py tests/services/ .mavis/plans/plan.yaml
# 不要 add points-v2*.spec 和 build/ —— 是 PyInstaller 失败残留
git commit -m "style(api/services): ruff --fix unused imports + nested-if to and-merged"
```

### 结论

- **ruff gate**：0 错 PASS
- **测试 gate**：107/107 PASS, 64% ≥ 60% PASS
- **E2E gate**：12/12 PASS PASS
- **mypy gate**：103 错（pre-existing，文档化，不硬修）WARN
- **PyInstaller gate**：环境 bug 阻塞，不在 v2 项目范围 WARN

**整体**：除 mypy 与 PyInstaller 外，所有硬性 gate 通过。verifier 建议 owner：
1. commit 当前 working tree（owner ruff --fix + SIM102 fix）
2. 按 §6 修复 mypy（建议优先加 `[[tool.mypy.overrides]]` for PySide6 全模块）
3. 升级 Python 至 ≥ 3.10.12 后重试 PyInstaller
4. （可选）补 `points_service` / `user_service` 审计与通知回调
