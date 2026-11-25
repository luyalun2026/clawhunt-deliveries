# 2113 · S6-BRAND-001 上线后品牌落地情况审计与偏差清单

## 思路

审计输入（品牌规范、40+ 截图）由核心团队提供。本包交付**可复现审计管线 + 全量虚构演示语料**：
44 张虚构界面/物料 SVG（固定种子，重跑逐字节一致）+ 虚构品牌规范，全流程跑通三条验收标准；
正式材料到位后，同一管线换 `corpus/` 输入目录直接重跑。

## 运行方法

```bash
pip install -r requirements.txt    # pyyaml / openpyxl / pytest
python _gen_corpus.py              # 生成 44 张 SVG 语料 + manifest（已随包附带，可跳过）
python audit/audit_runner.py       # 8 类检查 -> output/deviations.json（182 条）
python audit/build_deviation_list.py   # -> output/deviation_list.xlsx + summary.json + 44 张标注 SVG
python audit/build_revision_suggestions.py  # -> output/revision_suggestions.md
python -m pytest tests -q          # 7 例测试
```

## 交付物

- `audit/measure_contrast.py`：WCAG 2.1 相对亮度公式实测（正文 ≥4.5:1 / ≥24px 大字 ≥3:1）
- `audit/audit_runner.py`：8 类问题检查（色板 / 对比度 / 字体字号 / logo / 图标笔画 / 栅格 / 插图色板 / 文案禁用词）
- `audit/annotate.py`：标注副本（红框 + `#编号 问题类型` 徽标）
- `audit/build_deviation_list.py`：偏差清单 Excel（编号/文件/位置/问题类型/描述/严重级别/频次/判定/章节/对比度实测/工具名/标注文件）
- `audit/build_revision_suggestions.py`：按规范章节归类的修订建议，每条回链偏差编号
- `corpus/spec.yaml`：虚构品牌规范（8 章）；`corpus/shots/`：44 张 SVG（工作台 12 / 小程序 12 / 官网 6 / 海报 5 / 公众号头图 5 / 补充 4）
- `output/`：实跑产物（deviation_list.xlsx、deviations.json、summary.json、revision_suggestions.md、annotated/）

## 实测结论（数字由脚本自动提取）

- 44 张语料共 **182 条偏差**：对比度 55 / 栅格 50 / 越界色 29 / 字体 9 / logo 变形 9 / 字号层级 7 / logo 过小 7 / 插图色板 8 / 图标笔画 4 / 文案禁用词 4
- 严重级别：高 64 / 中 40 / 低 78；判定规则表驱动（规范覆盖→执行偏差，未覆盖→规范缺失）

## 验收标准落点

| AC | 证据 |
|---|---|
| 1 ≥40 处抽样且要素齐全 | `test_ac1_at_least_40_samples_with_fields`（实测 182 条，每条含标注框/位置/类型/级别） |
| 2 对比度实测值+工具名 | `test_ac2_contrast_records_have_tool_and_value`（55 条，含 ratio/required/工具名，抽样板复算） |
| 3 修订建议按章节+回链编号 | `test_ac3_revision_suggestions_link_ids`（8 章全部出现，182 个编号全回链） |

## 边界用例

fill=none 元素跳过对比度计算、≥24px 按 3:1 判定、标注框负坐标/小尺寸钳制、规范未覆盖类型判「规范缺失」。

## 对接点

正式审计时将 `corpus/spec.yaml` 替换为客户规范条目化结果、`corpus/shots/` 替换为截图（SVG 检查器按 SVG 通用属性工作；位图截图需先转 SVG 包装或扩展 PIL 采样器，README 中已注明）。
