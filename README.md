# S4-FIN-002 · 签约事件分期算法与尾差处理（交付页）

**交付物**：`schedule.py`（纯函数分期算法 + 幂等事件消费者桩）、`check_no_float.py`（AST 静态检查）、
10 份样例合同与期望分期黄金文件（`sample_contracts/`）

## 验收标准逐条对应

| # | 验收标准 | 结果 | 证据 |
|---|---|---|---|
| 1 | 12 个月季付 → 租金 4 期、会籍 4 期、押金 1 期，逐分相等 | ✅ `test_12m_quarter_contract` | `evidence/pytest.txt` |
| 2 | hypothesis 随机 200 份合同（含尾期折算），Σ分期 == 总额 | ✅ `test_hypothesis_200_contracts`（max_examples=200） | `evidence/pytest.txt` |
| 3 | 同一事件重复投递 3 次只生成 1 个计划 | ✅ `test_idempotent_event_redelivery`（双重防护：source_event_id 唯一 + 同合同 active 唯一） | `evidence/pytest.txt` |
| 4 | 金额模块无 float | ✅ `check_no_float.py` AST 扫描 schedule.py 违规 0 处；且检查器自身对违规样本正确报警 | `evidence/pytest.txt` |

**pytest 汇总：11 passed**。另：10 份样例与 `reference.py`（独立参照算法）逐字段一致 10/10
（`evidence/samples_run.txt`）。

## 算法要点

- 完整周期判据：周期末 <= 合同期末；最后一期恰好覆盖到期末时按周期金额收取，`kind=regular`，不标 `tail`。
- 整期金额 = 周期金额原值（整数分，不做除法）；尾期（不足一个完整周期）日金额 = 月金额 × 12 ÷ 365，
  Decimal 计算后 ROUND_HALF_UP **取整到 1 分**（`prorate_tail()`）。
- 总额由规则推导（n_full × 周期金额 + 尾期折算）；`total_cents` 可省略，显式给出时只允许 ±5 分舍入尾差
  计入最后一期，超差抛 `FeeTotalMismatch`，不静默吸收。
- 交叉验证：`reference.py` 用整数 divmod 独立实现同一规则，样例期望值与 hypothesis 期望值均由它生成。
- 到期日：首期 = 首付款日；后续 = 周期开始日 − advance_days；押金独立 1 行。
- 多年合同输出 first_year_amount_cents（起始 12 个月内的分期之和）。
- 幂等：`PlanStore` 以 source_event_id 唯一 + 同合同仅一个 active 计划双重防护；
  生产替换为 PostgreSQL 唯一索引/部分唯一索引，接口不变。

## 运行

```bash
python -m pytest tests/ -v          # 全部测试（含 hypothesis 200 例）
python check_no_float.py schedule.py # 无 float 静态检查（违规退出码 1）
python make_samples.py              # 重新生成 10 份样例与黄金文件
```

对接点：事件来源 S3-SALES（`contract.signed`），当前以样例事件 JSON 驱动（桩）；
落库层为 PostgreSQL（金额一律 BigInteger 分），README 随仓库维护。
全部数据虚构，无客户名称，无 float。
