# -*- coding: utf-8 -*-
"""构造虚构评测集（30 篇，全部虚构）：模板化正文 + 构造期即确定的标签。

标签与正文来自同一组参数（先定日期，再渲染成句），保证评测独立于抽取器实现。
运行：python eval/build_eval_set.py → 写出 eval/eval_set.json
"""
import json
import os
import random
from datetime import date, datetime, timedelta

random.seed(20260101)

ORG = ["江城科技创新协会", "临湖产业发展局", "南岭商务联合会", "云溪数字经济园区"]
PROJECT = ["专精特新培育补贴", "中小企业数字化改造资助", "绿色工厂奖励", "研发投入奖补"]

docs = []


def add(doc_id, text, publish: date, expected, earliest):
    docs.append({
        "id": doc_id,
        "text": text,
        "publish_date": publish.strftime("%Y-%m-%d"),
        "expected_deadlines": expected,          # [{deadline_type, deadline}]
        "expected_earliest_submission": earliest,  # "YYYY-MM-DD" 或 None
    })


def fmt(d: date):
    return "%d年%d月%d日" % (d.year, d.month, d.day)


# —— 绝对日期、单一 submission（8 篇）——
for i in range(8):
    pub = date(2026, 1, 5) + timedelta(days=i * 7)
    dl = pub + timedelta(days=30 + i * 5)
    ev = dl + timedelta(days=20)
    text = ("%s关于开展%s的通知。申报条件：在本地注册满两年的独立法人企业。"
            "申报材料：营业执照复印件、上年度审计报告。请各单位于%s前提交申报材料至受理窗口。"
            "本次活动评审会时间为%s。办理流程：线上提交、部门联审、公示。" %
            (ORG[i % 4], PROJECT[i % 4], fmt(dl), fmt(ev)))
    add("E%02d" % (i + 1), text, pub,
        [{"deadline_type": "submission", "deadline": dl.strftime("%Y-%m-%d")},
         {"deadline_type": "event_date", "deadline": ev.strftime("%Y-%m-%d")}],
        dl.strftime("%Y-%m-%d"))

# —— 相对日期（6 篇）——
for i in range(6):
    pub = date(2026, 2, 2) + timedelta(days=i * 6)
    n = 10 + i * 5
    dl = pub + timedelta(days=n)
    text = ("%s关于印发%s实施细则的通知。支持对象为园区内规上企业。"
            "企业需提交近三年研发费用清单。本通知自发布之日起%d日内完成申报。"
            "资助标准为不超过200万元。" %
            (ORG[(i + 1) % 4], PROJECT[(i + 1) % 4], n))
    add("E%02d" % (i + 9), text, pub,
        [{"deadline_type": "submission", "deadline": dl.strftime("%Y-%m-%d")}],
        dl.strftime("%Y-%m-%d"))

# —— 相对日期、工作日（4 篇）——
for i in range(4):
    pub = date(2026, 3, 2) + timedelta(days=i * 7)
    n = 15 + i * 5
    cur, added = pub, 0
    while added < n:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            added += 1
    text = ("%s关于组织%s申报的工作方案。申报范围包括规下转规上企业。"
            "材料包括申请表与佐证材料。请自印发之日起%d个工作日内报送。"
            "有效期至2027年12月31日。" %
            (ORG[(i + 2) % 4], PROJECT[(i + 2) % 4], n))
    add("E%02d" % (i + 15), text, pub,
        [{"deadline_type": "submission", "deadline": cur.strftime("%Y-%m-%d")},
         {"deadline_type": "effective_until", "deadline": "2027-12-31"}],
        cur.strftime("%Y-%m-%d"))

# —— 多个申报截止（6 篇）——
for i in range(6):
    pub = date(2026, 4, 1) + timedelta(days=i * 5)
    first = pub + timedelta(days=20 + i * 3)
    second = first + timedelta(days=15)
    text = ("%s关于%s第二批申报的公告。申报条件：上年度营收不低于5000万元。"
            "第一阶段申报截止日期为%s；因场地受限，第二阶段受理截止顺延至%s。"
            "申报材料：项目可行性报告。" %
            (ORG[(i + 3) % 4], PROJECT[(i + 3) % 4], fmt(first), fmt(second)))
    add("E%02d" % (i + 19), text, pub,
        [{"deadline_type": "submission", "deadline": first.strftime("%Y-%m-%d")},
         {"deadline_type": "submission", "deadline": second.strftime("%Y-%m-%d")}],
        first.strftime("%Y-%m-%d"))

# —— 只有有效期/活动日期、无申报截止（3 篇）——
for i in range(3):
    pub = date(2026, 5, 4) + timedelta(days=i * 10)
    ev = pub + timedelta(days=25)
    text = ("%s关于举办供需对接会的预通知。适用于园区注册企业。"
            "活动日期为%s。本通知有效期至2026年12月31日。" %
            (ORG[i % 4], fmt(ev)))
    add("E%02d" % (i + 25), text, pub,
        [{"deadline_type": "event_date", "deadline": ev.strftime("%Y-%m-%d")},
         {"deadline_type": "effective_until", "deadline": "2026-12-31"}],
        None)

# —— 干扰项：金额与条件密集、日期出现在条件描述中但不带截止语义（3 篇）——
for i in range(3):
    pub = date(2026, 6, 1) + timedelta(days=i * 9)
    dl = pub + timedelta(days=18)
    text = ("{org}关于{proj}的补充说明。金额规则：单个企业补贴不超过150万元，比例为实际投资的30%。"
            "2026年3月1日以前注册的企业适用于本条。请于{dl}前提交材料。"
            "流程如下：初审、复审、拨付。").format(org=ORG[(i + 1) % 4],
                                                  proj=PROJECT[(i + 1) % 4], dl=fmt(dl))
    add("E%02d" % (i + 28), text, pub,
        [{"deadline_type": "submission", "deadline": dl.strftime("%Y-%m-%d")}],
        dl.strftime("%Y-%m-%d"))

out = {"description": "虚构评测集（30 篇，全部虚构，无真实个人信息或企业信息）",
       "publish_note": "相对日期类条目，抽取时以 publish_date 为程序推算基准",
       "docs": docs}
path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_set.json")
with open(path, "w", encoding="utf-8", newline="\n") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("docs:", len(docs))
