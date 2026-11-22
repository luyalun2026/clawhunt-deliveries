# 多会所数据隔离越权测试集（7 类资源 × 3 类账号）

## 一句话
对会员空间平台的机构（org）/会所（site）两级隔离做自动化越权测试：105 格期望矩阵全覆盖，
外加 18 个绕过用例（参数伪造 / 间接读取 / 批量导出）与 6 个边界用例，共 **129 个用例**。

## 目录
```
access_matrix.yaml      期望矩阵（JSON 兼容 YAML 子集，7 资源 × 3 账号 × 5 场景，空格 0）
seed.py                 虚构数据：2 机构 / 3 会所 / 每会所 3 类账号 / 7 资源各 3 条 + 软删除
service.py              被测接口桩（鉴权与数据范围只有两个出口：scope_sites / writable_sites）
make_matrix.py          矩阵生成器（改规则后重跑即可再生）
tests/test_matrix.py    矩阵驱动用例（105 例）
tests/test_bypass.py    绕过与边界（24 例）
run_all.py              一键跑测 + 生成 reports/junit.xml、outputs/run-report.md、outputs/verify.json
```

## 运行
```bash
python make_matrix.py          # 重新生成矩阵（可选）
python run_all.py              # 跑全部用例并生成报告与证据
```

## 期望值语义
- `allow`：200 且结果仅含允许范围内的数据；
- `deny`：403 或 404，响应体 code ∈ {FORBIDDEN, NOT_FOUND}；
- `filtered`：200 但结果集不含任何范围外记录（不得以「200 = 通过」草率判定）。

## 对接真实环境
把 `service.py` 的 `request()` 换成 HTTP 调用（`BASE_URL` 指向测试环境，真实系统需提供 `Authorization`），
矩阵与用例文件无需改动。对接点：鉴权凭证注入、分页参数名（`page` / `page_size`）、导出接口路径。

## 合规声明
所有数据均为虚构（示例机构甲/乙、示例一号会所），不含任何真实企业或个人信息；
所有请求只发往测试环境；未引入任何第三方 SDK。
