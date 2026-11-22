# -*- coding: utf-8 -*-
"""工单 #2221：政策关键条件与截止日期结构化抽取（intel.conditions.v1）。

构成：
  - intel/prompt_v1.md        生产提示词（LLM 调用版）
  - app/extractor.py          调用编排 + 后置校验（source_text 逐字回验、丢弃审计）
  - app/relative_date.py      相对日期推算（程序按发布日期计算，标注「程序推算」）
  - app/schema_v1.json        JSON Schema
  - eval/eval_set.json        虚构评测集（30 篇，全部虚构，无真实信息）
  - eval/run_eval.py          评测脚本：截止日期抽取准确率

离线口径说明：本包的「模型」为确定性规则实现（进程内等价），接口与 LLM 版一致
（extract(text, publish_date) → 同构 JSON）。生产替换为真实 LLM 调用，提示词见
intel/prompt_v1.md；后置校验与相对日期推算两段为纯程序逻辑，两种模式下共用。
"""
