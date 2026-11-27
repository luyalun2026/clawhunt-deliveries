# #2983 · P95 分析报告模板与自动生成

把 k6 / Locust 的压测结果文件转成**单文件 HTML 性能报告**：测试目的、环境、场景、并发曲线、各接口 P50/P95/P99、错误率、阈值对比、与上一轮对比、结论与建议。HTML 内嵌 CSS 与 SVG，无外部依赖，可直接转发。

## 快速开始

```bash
python -m pytest tests -q                 # 16 例
python verify.py --skip-load              # 用已有结果重生成 outputs/report.html + verify.json + index.html
python verify.py --seconds 10             # 重新压测 10 秒后再生成
```

生成报告（两种输入均可）：

```bash
# Locust：--csv=<prefix> 产生的 prefix_stats.csv / prefix_stats_history.csv
python -m perfreport.cli --locust samples/locust/run --thresholds thresholds.json \
       --previous samples/previous/prev.json --env env.json --scenario "混合读" \
       --title "性能测试报告" -o report.html --json-out summary.json

# k6：--out json 的 JSONL（可算端点分位）；或 --summary-export 的全局聚合（回退）
python -m perfreport.cli --k6-jsonl result.json --thresholds thresholds.json -o report.html
python -m perfreport.cli --k6-summary summary.json -o report.html
```

## 目录

| 路径 | 说明 |
|---|---|
| `perfreport/model.py` | 统一结果模型与分位数（线性插值，与 k6 p(n) 口径一致） |
| `perfreport/k6.py` | k6 JSONL（按 `tags.name` 分组）与 summary-export 解析 |
| `perfreport/locust.py` | Locust `_stats.csv` / `_stats_history.csv` / `_failures.csv` |
| `perfreport/thresholds.py` | 阈值（全局 + 端点覆盖）、超阈判定、与上轮 Δ 计算 |
| `perfreport/render.py` | 单文件 HTML：内联 CSS、并发曲线 SVG、分位柱状图 SVG |
| `perfreport/cli.py` | 命令行入口 |
| `tools/stub_server.py` | 被测桩服务（独立运行模式，供真实 Locust / k6 压测） |
| `tools/k6_script.js` | k6 v2.4.0 压测脚本（三接口混合读，8 VU / 20s） |
| `locustfile.py` | Locust 2.47.0 压测脚本（三接口混合读，8 用户 / 20s） |
| `tools/loadgen.py` | 离线备用负载发生器（无 k6/Locust 环境时才使用，样例采集不依赖它） |
| `samples/` | 真实采集的结果文件（当前轮、基线轮、k6 summary 样例） |
| `outputs/` | `report.html` 样例、`summary.json`、`verify.json` |

## 阈值格式

```json
{"global": {"p50_ms": 60, "p95_ms": 120, "error_rate": 0.05},
 "endpoints": {"GET /api/members": {"p95_ms": 40}}}
```

端点级配置优先于全局；实测值 **等于** 阈值判为达标（`<=`），边界有专门用例。

## 三条验收的落点

1. **阈值与上一轮对比**：报告第五节列出全部超阈项（接口 / 指标 / 实测 / 阈值），第六节列出较上一轮恶化 > 10% 的指标（上轮值 / 本轮值 / 变化率）；Δ 由 `thresholds.compare()` 计算，`--previous` 接受本工具 `--json-out` 的产物。
2. **单文件、无外部依赖**：`test_single_file_no_external_refs` 断言 HTML 中 `http://`、`https://`、`<script src`、`rel="stylesheet"`、`@import`、`<iframe>` 全部为 0 处；`verify.json` 记录实测 `external_refs`。
3. **样例由真实压测结果生成**：`samples/locust/run_stats.csv` 等三张 CSV 由 **Locust 2.47.0**（`locust --headless --csv=samples/locust/run`）对本机桩服务真实压测产生；`samples/k6/summary.json` 与 `samples/k6/result.jsonl` 由 **k6 v2.4.0**（`--summary-export` / `--out json`）真实压测产生；`outputs/report.html` 由 Locust CSV 生成。基线轮 `samples/previous/` 为同环境、延迟系数 2.2 的真实 Locust 轮。工具版本与完整命令见下方「采集与复现」。

## 采集与复现（真实工具，2026-11-28）

```bash
pip install locust                 # Locust 2.47.0
# k6 v2.4.0 单二进制：https://github.com/grafana/k6/releases

# ① 起被测桩服务（三接口：4ms/12ms/35ms 基线延迟 + 2% 503）
DELAY_SCALE=1.0 python tools/stub_server.py --port 8901

# ② Locust 2.47.0 当前轮
locust -f locustfile.py --headless -u 8 -r 2 -t 20s \
       --host http://127.0.0.1:8901 --csv=samples/locust/run

# ③ 基线轮（另起 DELAY_SCALE=2.2 python tools/stub_server.py --port 8902）
locust -f locustfile.py --headless -u 8 -r 2 -t 20s \
       --host http://127.0.0.1:8902 --csv=samples/previous/run
python -m perfreport.cli --locust samples/previous/run --thresholds thresholds.json \
       -o samples/previous/baseline.html --json-out samples/previous/prev.json

# ④ k6 v2.4.0
k6 run --vus 8 --duration 20s --summary-export=samples/k6/summary.json \
       --out json=samples/k6/result.jsonl tools/k6_script.js

# ⑤ 由真实 Locust CSV 生成报告
python -m perfreport.cli --locust samples/locust/run --thresholds thresholds.json \
       --previous samples/previous/prev.json --env env.json --scenario "混合读场景：成员列表 + 商机列表 + 订单导出" \
       --title "性能测试报告 · 会员空间 API" -o outputs/report.html --json-out outputs/summary.json
```

## 环境说明（如实披露）

- 采集侧全部为真实工具产物：**Locust 2.47.0**（pip 安装）与 **k6 v2.4.0**（官方单二进制），被测对象为本机桩服务（`tools/stub_server.py`，stdlib `http.server`）；被测服务模拟 4ms / 12ms / 35ms 基线延迟与 2% 503。
- `tools/loadgen.py` 保留为**离线备用**负载发生器（无 k6/Locust 环境时才使用）；`samples/` 下当前不含任何 loadgen 产物。
- 报告中 P99 尾部来自 Windows 计时粒度与本机线程调度，属采集环境特征，已在第六节与结论中说明；门槛判定使用 P50/P95/错误率三项，P99 仅作参考。

## 复现

```bash
git clone --branch 2983 https://github.com/luyalun2026/clawhunt-deliveries.git
cd clawhunt-deliveries
python -m pytest tests -q        # 16 passed
python verify.py --skip-load     # 重生成报告，打印 verdict 与请求数
```

提交与校验值见 `SHA256SUMS`。
