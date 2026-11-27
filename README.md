# S3-TRK-001 · 埋点事件字典与属性 Schema（首批 13 个核心事件）

> 会员空间平台 · Stage iii 数据采集 · track 模块
> 字典单源（YAML）→ 生成脚本 → Markdown / TypeScript / JSON Schema 三端产物
> pytest 10 用例全过

## 一、验收标准逐条对应

| # | 验收标准 | 实现 | 证据 |
|---|---|---|---|
| 1 | 字典包含 13 个事件，且每个事件都有 props Schema | `load_dictionary` 断言事件数==13 且逐事件 props 为 type=object 的 JSON Schema；13 个事件名与订单清单逐一对应 | `test_ac1_dictionary_13_events_with_props_schema` ✅ |
| 2 | 生成脚本输出 Markdown 与 .d.ts 文件，CI 中生成结果与仓库内文件一致 | `generate.py` 输出 docs/event_dictionary.md、sdk/events.d.ts、server/schema/*.json（13 份）；测试在 tmp 目录重跑生成并与仓库内文件**逐字节比对**（生成时间不写入，保证可复现） | `test_ac2_regenerated_files_byte_identical` ✅ |
| 3 | 字段名命中个人信息黑名单时生成脚本报错（测试） | 黑名单写在 YAML 顶部 blacklist 段；加载即校验，命中 phone/手机号 等即 SystemExit 并打印事件名与违规字段 | `test_ac3_blacklist_field_raises` ✅、`test_ac3_blacklist_chinese_variant_raises` ✅ |

补充：重名事件/非法状态/非法版本号/props 非 object 报错；keyword 为唯一放行的搜索词字段；deprecated 事件必须带 deprecated_reason；服务端 Schema required 与 additionalProperties:false 校验。

## 二、运行方法

```bash
pip install pytest pyyaml
python track/generate.py            # 生成三端产物
python -m pytest tests/ -v          # 10 passed
```

## 三、交付物

- `track/event_dictionary.yaml` — 单一事实源（13 事件：app_launch、page_view、auth_success、auth_apply、resource_view、resource_publish、connect_request、event_view、event_register、event_checkin、faq_ask、faq_feedback、share）
- `track/generate.py` — 生成脚本（加载即校验：数量/重名/黑名单/Schema 合法性）
- `docs/event_dictionary.md` — 生成的 Markdown 文档
- `sdk/events.d.ts` — 生成的 TypeScript 类型（enum → 联合类型，required 字段非可选）
- `server/schema/*.json` — 每事件一份服务端校验 JSON Schema（additionalProperties:false）
- `tests/test_dictionary.py` — 10 用例

### 版本与评审流程
版本号 semver；变更流程：改 YAML → 数据管理员评审 → 合版 → 重跑 generate.py → 一致性测试（AC2）通过。README 内记录对接点：小程序 SDK（编译期 .d.ts）、服务端校验（JSON Schema）。

### 数据与保密
字典全部为虚构负责人（数据组-李工/张工/王工 虚构），字段只允许 keyword 搜索词，严禁手机号/证件号/姓名/邮箱。

## 四、测试结果

见 `outputs/pytest_main.txt`（10 passed / 0 failed）、`outputs/verify.json`（数字由 pytest 输出自动提取）、`SHA256SUMS`。
