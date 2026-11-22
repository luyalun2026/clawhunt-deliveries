# 金额注入矩阵（实跑生成）

对每个写接口在请求体中同时注入 6 个只读金额字段，期望 422 或字段被忽略：

| 接口 | 实测路径 | 结果 |
|---|---|---|
| `PATCH /api/sales/contracts/{id}` | `/api/sales/contracts/contract_lead_a1` | 422 READONLY_FIELD |
| `PATCH /api/sales/leads/{id}` | `/api/sales/leads/lead_a1` | 422 READONLY_FIELD |
| `PATCH /api/sales/quotes/{id}` | `/api/sales/quotes/quote_lead_a1` | 422 READONLY_FIELD |
| `POST /api/sales/attachments/presign` | `/api/sales/attachments/presign` | N/A 无金额语义（200 字段被忽略） |
| `POST /api/sales/esign/callback` | `/api/sales/esign/callback` | N/A 无金额语义（401 SIGNATURE_INVALID） |
| `POST /api/sales/quotes` | `/api/sales/quotes` | 422 READONLY_FIELD |
| `POST /api/sales/quotes/{id}/approve` | `/api/sales/quotes/quote_lead_a1/approve` | 422 READONLY_FIELD |
| `PUT /api/sales/leads/{id}` | `/api/sales/leads/lead_a1` | 422 READONLY_FIELD |
| `PUT /api/sales/quotes/{id}` | `/api/sales/quotes/quote_lead_a1` | 422 READONLY_FIELD |

金额相关写接口共 7 个，其中 422 拒绝或字段被忽略：7；另 2 个接口无金额语义（N/A）。
