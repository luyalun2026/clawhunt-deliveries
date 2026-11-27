# S5-INTEL-012 · 发布日期解析与发布机构名称规范化

> 会员空间平台 · Stage v AI 辅助工具 · 情报采集规范化
> 纯函数实现（仅标准库，零第三方依赖）· pytest 12 用例全过

## 一、验收标准逐条对应

| # | 验收标准 | 实现 | 证据 |
|---|---|---|---|
| 1 | 40 条日期用例（含中文数字、缺年份、跨年）解析结果全部正确 | 27 条显式（ISO/中文/汉字数字/斜杠/点分隔）+ 9 条缺年份推断 + 5 条 meta/URL = 41 条，全部参数化断言 (date, confidence, source) | `test_ac1_40plus_date_cases_all_correct` ✅ |
| 2 | 缺年份推断不会得到晚于抓取日期的日期（属性测试） | 固定种子随机 200 组 (月-日, 抓取日)，断言 `result <= fetched_at.date()`；跨年回退（12-31 对 1 月 5 日抓取 → 上一年） | `test_ac2_inferred_never_after_fetched` ✅ |
| 3 | 找不到日期时返回空并标记 need_manual_date，而不是抓取日期 | 正文/meta（article:published_time、PubDate）/URL 三处皆无 → `(None, 0.0, "none")`，抓取日期只参与年份推断绝不替代值 | `test_ac3_not_found_marks_need_manual` ✅ |

补充：汉字数字 〇/零 双写法与 十/二十/三十一 位权组合、闰年 02-29 推断年非闰年时宁缺勿错、全角半角归一化、非法输入（None/空串/乱码）不抛异常、机构 15 条用例（别名/部门后缀剥离/未命中回退来源名并标记 publisher_unverified）。

## 二、运行方法

```bash
pip install pytest
python -m pytest tests/ -v          # 12 passed
```

## 三、模块说明

- `app/normalize.py` — `normalize_date`（四级来源：body → meta → URL → none）、`normalize_publisher`（NFKC 归一化 → 部门后缀剥离 → 别名匹配 → 回退）、`_cn_to_digits`（汉字数字位权解析）。
- `app/aliases.yaml` — 虚构机构别名字典示例（3 组标准名 + 7 别名）。
- 置信度：显式年份 0.95 > meta 0.9 > URL 0.85 > 缺年份推断 0.6。

### 缺年份推断规则
推断年 = 抓取年；结果晚于抓取日则回退一年（source=body_inferred_year）。02-29 在非闰推断年直接 need_manual_date，绝不静默替代。

### 数据与保密
字典与用例全部为虚构名称，不含任何真实机构信息。

## 四、测试结果

见 `outputs/pytest_main.txt`（12 passed / 0 failed）、`outputs/verify.json`（数字由 pytest 输出自动提取）、`SHA256SUMS`。
