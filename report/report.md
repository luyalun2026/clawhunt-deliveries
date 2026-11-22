# S3-SALES-056 招商模块越权与金额篡改安全测试套件 — 测试执行报告

- 用例总数：**31**
- 通过：**31**｜失败：**0**｜错误：**0**｜跳过：**0**
- 总耗时：1.30 s
- 数据来源：`report/junit.xml`（pytest --junitxml 生成，本节数字由脚本自动提取）

## tests.test_01_idor_read（6 例）

| 用例 | 结果 |
|---|---|
| `test_consultant_cannot_read_peer_object[leads]` | PASS |
| `test_consultant_cannot_read_peer_object[follows]` | PASS |
| `test_consultant_cannot_read_peer_object[visits]` | PASS |
| `test_consultant_cannot_read_peer_object[quotes]` | PASS |
| `test_consultant_cannot_read_peer_object[contracts]` | PASS |
| `test_consultant_cannot_read_peer_object[attachments]` | PASS |

## tests.test_02_idor_write（5 例）

| 用例 | 结果 |
|---|---|
| `test_put_lead_of_peer_rejected` | PASS |
| `test_patch_lead_of_peer_rejected` | PASS |
| `test_put_quote_of_peer_rejected` | PASS |
| `test_patch_contract_of_peer_rejected` | PASS |
| `test_own_object_write_allowed_and_persisted` | PASS |

## tests.test_03_cross_org（4 例）

| 用例 | 结果 |
|---|---|
| `test_consultant_cross_org_404` | PASS |
| `test_supervisor_cross_org_404` | PASS |
| `test_cross_org_write_404` | PASS |
| `test_cross_org_public_pool_isolated` | PASS |

## tests.test_04_amount_inject（6 例）

| 用例 | 结果 |
|---|---|
| `test_amount_field_injection_rejected_on_create[final_monthly_cents]` | PASS |
| `test_amount_field_injection_rejected_on_create[contract_total_cents]` | PASS |
| `test_amount_field_injection_rejected_on_create[first_year_amount_cents]` | PASS |
| `test_amount_field_injection_rejected_on_create[deposit_cents]` | PASS |
| `test_concession_field_injection_rejected` | PASS |
| `test_created_quote_matches_engine` | PASS |

## tests.test_05_approval（4 例）

| 用例 | 结果 |
|---|---|
| `test_submitter_cannot_approve_own_quote` | PASS |
| `test_skipping_step_rejected` | PASS |
| `test_two_steps_pass_in_order` | PASS |
| `test_unknown_step_rejected` | PASS |

## tests.test_06_public_pool（2 例）

| 用例 | 结果 |
|---|---|
| `test_public_pool_has_no_full_phone` | PASS |
| `test_public_pool_uses_mask_format` | PASS |

## tests.test_07_presign（2 例）

| 用例 | 结果 |
|---|---|
| `test_token_valid_within_ttl` | PASS |
| `test_token_expired_after_300s` | PASS |

## tests.test_08_esign_forge（2 例）

| 用例 | 结果 |
|---|---|
| `test_forged_signature_rejected` | PASS |
| `test_valid_signature_accepted` | PASS |
