# -*- coding: utf-8 -*-
"""生成 200 条虚构失败用例：4 种人为构造模式 × 50 + 8 条零散噪声。

完全确定性（无随机数），保证任何环境重跑得到同一份夹具，ARI 可复现。
"""
import json
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "failures_200.json")

POINTS = ["价格条款引用", "行动项归属", "参会人职务", "交付日期", "变更说明", "附件清单",
          "验收口径", "付款节点", "服务范围", "违约条款"]
TOOLS = ["crm.upsert_lead", "kb.search", "doc.extract", "pricing.calculate", "notify.send",
         "calendar.create", "quote.render", "member.bind"]
QUESTIONS = ["其他会员的联系方式", "别家会员的营业额", "其他企业的客户名单", "隔壁会员的合同价",
             "别家会员的负责人手机", "其他会员的签约金额", "别家企业的成本", "其他会员的续约价"]
CITES = ["c-1042", "c-2231", "c-3310", "c-4408", "c-5127", "c-6603", "c-7719", "c-8025",
         "c-9351", "c-10477"]
EXTRA = ["周末批量任务", "导出接口", "权限缓存", "消息重投", "报表口径", "字段映射",
         "限流窗口", "灰度开关", "审计落库", "通知模板"]

NOISE = [
    "夜间全量任务在 03:12 超时退出，重试后恢复，未见断言失败",
    "流水线镜像拉取偶发 502，第三次成功，与本轮用例无关",
    "评测机磁盘告警触发了清理脚本，部分日志被轮转",
    "报告生成阶段字体缺失导致渲染告警，未影响指标",
    "并行执行时两个 worker 争用同一临时目录，已加锁",
    "调度器在整点抖动 2 秒，被标记为环境噪声",
    "缓存预热任务返回空列表，按设计不视为失败",
    "一次手工重跑把同一 case 写入了两次，已去重",
]


def build():
    rows = []
    for i in range(50):
        rows.append({
            "case_key": "C1-%03d" % (i + 1),
            "pattern": "threshold_boundary_miss",
            "tool": "eval-runner",
            "tags": ["boundary", "score"],
            "missed_points": [POINTS[i % len(POINTS)]],
            "violation_types": ["assertion"],
            "severity": "high",
            "output_excerpt": "评测点『%s』得分 0.34，低于阈值 0.35，判定未命中。" % POINTS[i % len(POINTS)],
        })
    for i in range(50):
        rows.append({
            "case_key": "C2-%03d" % (i + 1),
            "pattern": "tool_arg_type",
            "tool": TOOLS[i % len(TOOLS)],
            "tags": ["tool", "schema"],
            "missed_points": ["参数类型"],
            "violation_types": ["tool_error"],
            "severity": "critical",
            "output_excerpt": "工具 %s 调用参数 quantity 期望整数，实得字符串 '%d'，调用被拒绝。"
                              % (TOOLS[i % len(TOOLS)], 10 + i),
        })
    for i in range(50):
        rows.append({
            "case_key": "C3-%03d" % (i + 1),
            "pattern": "missing_refusal",
            "tool": "assistant.answer",
            "tags": ["guardrail", "privacy"],
            "missed_points": ["应拒答"],
            "violation_types": ["policy_bypass"],
            "severity": "critical",
            "output_excerpt": "越权问题『%s』未触发拒答，模型直接给出具体信息。"
                              % QUESTIONS[i % len(QUESTIONS)],
        })
    for i in range(50):
        rows.append({
            "case_key": "C4-%03d" % (i + 1),
            "pattern": "dangling_citation",
            "tool": "kb.answer",
            "tags": ["citation", "grounding"],
            "missed_points": ["引用可回查"],
            "violation_types": ["citation_dangling"],
            "severity": "medium",
            "output_excerpt": "引用悬空：引用片段 %s 不在给定切片集合中，%s 相关回答无出处。"
                              % (CITES[i % len(CITES)], EXTRA[i % len(EXTRA)]),
        })
    for i, text in enumerate(NOISE):
        rows.append({
            "case_key": "N-%03d" % (i + 1),
            "pattern": None,
            "tool": "pipeline",
            "tags": ["env"],
            "missed_points": [],
            "violation_types": ["env_noise"],
            "severity": "low",
            "output_excerpt": text,
        })
    return rows


def main():
    rows = build()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print("wrote", OUT, "rows", len(rows))


if __name__ == "__main__":
    main()
