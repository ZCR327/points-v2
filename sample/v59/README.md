# v5.9 Sample Data

小型样本数据用于：
- **CI** 集成测试（`.github/workflows/ci.yml` 的 `migration` job 在 Linux 上跑真迁移）
- **本地回归** 快速验证迁移流程，不依赖你本地的真实 v5.9 项目

## 内容

- `marks.json` — 3 个用户：admin (super_admin) / alice (user) / bob (user)
- `points_history.json` — 3 条流水：alice 50 → 70（两次挣分），bob 30

## 跑

```bash
pip install -e ".[dev]"

tmp_dir=$(mktemp -d)
python -m points_v2.migrations.from_v5_9 \
    --source sample/v59 \
    --target "$tmp_dir"
cat "$tmp_dir/migration_report.json"
ls "$tmp_dir"
```

期望：3/3 用户导入，3/3 records 导入，0 错误。
alice 最终积分 70，bob 30，admin 0。
