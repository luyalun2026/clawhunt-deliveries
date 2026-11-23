# #2837 房态 / 租约 / 合同台账三方一致性核对脚本

只读核对脚本 `e2e/tools/reconcile_rooms.py`：读取房态、租约与合同台账，逐项比对后输出差异 CSV，有差异时以非零码退出。

## 一键复现

```bash
git clone --branch 2837 https://github.com/luyalun2026/clawhunt-deliveries.git
cd clawhunt-deliveries
python verify.py
```

`verify.py` 内部执行 `pytest tests -q` → 解析 junit → 生成 `outputs/verify.json` 与 `outputs/run-report.md`。数字全部自动提取，无手写。

单独运行脚本：

```bash
python e2e/tools/reconcile_rooms.py --fixtures tests/fixtures/inconsistent --as-of 2026-11-23 --out out/diff.csv
python e2e/tools/reconcile_rooms.py --base-url http://127.0.0.1:8000 --as-of 2026-11-23 --out out/diff.csv
```

## 退出码

| 码 | 含义 |
|---|---|
| 0 | 无差异（CSV 只有表头） |
| 2 | 检出差异 |
| 3 | 取数失败（网络/夹具缺失） |

## 核对规则

| type | 判定 | expected / actual |
|---|---|---|
| `leased_without_contract` | 办公室已租但无生效合同 | 有效合同 / 无 |
| `contract_space_not_leased` | 生效合同对应空间非已租 | leased / 实际房态 |
| `expired_contract_room_leased` | 合同已到期但房间仍为已租 | vacant / leased |
| `seat_sum_mismatch` | 工位区已租工位数 ≠ 生效合同工位数之和 | 合同合计 / 房态值 |
| `occupancy_mismatch` | 出租率重算与驾驶舱偏差 > 50bp | 驾驶舱 bp / 重算 bp |
| `tenant_mismatch` | 房态租户与生效合同租户不一致 | 合同租户 / 房态租户 |
| `expire_date_mismatch` | 房态到期日与合同结束日不一致 | 合同日期 / 房态日期 |
| `duplicate_active_contract` | 同一**办公室**存在多份生效合同 | 1 / 实际份数 |

出租率口径：`已租工位数 ÷ 可租工位数`，以基点（bp）整数比较，容差 50bp。工位区允许多份生效合同（不同企业分租不同工位），故「重复合同」规则只适用于独立办公室。

## 只读保证

`ReadOnlyClient` 只暴露 `get()`，`post/put/patch/delete` 方法体统一 `raise ReadOnlyViolation` —— 结构性约束，不依赖调用方自觉。测试断言调用方法集 ⊆ `{GET}`，并对源码 grep `INSERT/UPDATE/DELETE FROM` 结果为空。

## 结构

| 文件 | 说明 |
|---|---|
| `e2e/tools/reconcile_rooms.py` | 主脚本：规范化 → 核对 → CSV → 退出码 |
| `e2e/tools/readonly_client.py` | 只读客户端，支持 `--base-url` 与 `--fixtures` 两种取数模式 |
| `tests/make_fixtures.py` | 夹具生成（全部虚构数据） |
| `tests/test_reconcile_rooms.py` | 17 例：AC1–AC4 + 边界 5 例 + CLI 退出码 |
| `out/reconcile_diff.csv` | 差异 CSV 样例（5 行，UTF-8-SIG，Excel 直开） |
| `verify.py` | 一键复现 + 报告生成 |

## 对接点（mock → 真实接口）

三个取数函数集中在 `readonly_client.py` 末尾：

| 方法 | 生产端点 | 返回 |
|---|---|---|
| `rooms()` | `GET /api/space/rooms` | `{"items":[...]}`，含 `id/kind/status/tenant_id/expire_date/seat_total/seat_leased/deleted_at` |
| `contracts()` | `GET /api/contracts` | `{"items":[...]}`，含 `id/status/tenant_id/space_id/seats/start_date/end_date` |
| `dashboard(as_of)` | `GET /api/dashboard/metrics?as_of=` | `{"occupancy_rate_bp":int}` |

替换为真实接口只需改这三处，核对逻辑不动。字段缺失时按「不可判定」跳过，不误报。

## 边界处理

- 空数据集：exit 0，不误报。
- 软删除房间（`deleted_at` 非空）：不参与比对，不计入分母。
- 同一办公室双生效合同：输出 `duplicate_active_contract`。
- 到期日相差 1 天：按日期比较（非时间戳），精确检出。
- 驾驶舱接口不可用：stderr 告警，其余规则照常，不崩溃。
- CLI 夹具路径不存在：exit 3。

## 依赖

Python 3.11+ 标准库 + pytest。全部数据虚构，不含真实企业与个人信息。
