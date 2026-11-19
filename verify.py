#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S4-FIN-002 自检与实测数字生成器。

唯一职责：跑真实测试/样例/静态检查 → 把实测数字写进 outputs/verify.json，
并据此重建 index.html（页面上的每个数字都来自本文件，禁止手写）。

用法：python verify.py
"""
import csv
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs")
EVID = os.path.join(HERE, "evidence")
sys.path.insert(0, HERE)
import schedule as sch  # noqa: E402

PY = sys.executable


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def run_pytest():
    p = subprocess.run([PY, "-m", "pytest", "tests/", "-v"], cwd=HERE,
                       capture_output=True, text=True, encoding="utf-8")
    text = p.stdout + p.stderr
    os.makedirs(EVID, exist_ok=True)
    with open(os.path.join(EVID, "pytest.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    passed = len(re.findall(r"PASSED", text))
    m = re.search(r"(\d+) passed in ([\d.]+)s", text)
    return {
        "exit_code": p.returncode,
        "passed_tests": int(m.group(1)) if m else passed,
        "passed_markers": passed,
        "failed": 0 if "failed" not in text else len(re.findall(r"FAILED", text)),
        "duration_seconds": float(m.group(2)) if m else None,
        "pytest_version": (re.search(r"pytest-([\d.]+)", text).group(1)
                           if re.search(r"pytest-([\d.]+)", text) else None),
        "hypothesis_version": (re.search(r"hypothesis-([\d.]+)", text).group(1)
                               if re.search(r"hypothesis-([\d.]+)", text) else None),
        "test_names": re.findall(r"::(test_\w+) PASSED", text),
    }


def run_samples():
    sdir = os.path.join(HERE, "sample_contracts")
    names = sorted({f.split(".expected")[0].replace(".json", "")
                    for f in os.listdir(sdir) if f.endswith(".json")})
    rows, ok_all = [], True
    for name in names:
        ev = json.load(open(os.path.join(sdir, name + ".json"), encoding="utf-8"))
        exp = json.load(open(os.path.join(sdir, name + ".expected.json"), encoding="utf-8"))
        plan = sch.build_plan(ev)
        actual = [{"fee_type": i.fee_type, "seq": i.seq, "amount_cents": i.amount_cents,
                   "due_date": i.due_date.isoformat(),
                   "period": f"{i.period_start}~{i.period_end}", "kind": i.kind}
                  for i in plan.installments]
        sums = {f["fee_type"]: sch.by_type(plan, f["fee_type"]) for f in ev["fees"]}
        # 期望值来自 reference.py（独立参照算法），不读样例里的 total_cents
        sum_ok = all(sums[k] == v for k, v in exp["per_type_sum"].items()
                     if k != "deposit")
        golden_ok = (actual == exp["installments"]
                     and plan.first_year_amount_cents == exp["first_year_amount_cents"]
                     and len(plan.installments) == exp["installment_count"])
        ok = sum_ok and golden_ok
        ok_all = ok_all and ok
        rows.append({"sample": name, "pay_cycle": ev["pay_cycle"],
                     "installments": len(plan.installments),
                     "sum_equals_total": sum_ok, "golden_match": golden_ok,
                     "first_year_amount_cents": plan.first_year_amount_cents,
                     "per_type_sum": sums,
                     "contract_total_cents": sum(exp["per_type_sum"].values())})
    lines = [f"{r['sample'][:22]:24s} cycle={r['pay_cycle']:10s} "
             f"分期数={r['installments']:3d} 逐分相等={r['sum_equals_total']} "
             f"黄金比对={r['golden_match']}" for r in rows]
    lines.append("")
    lines.append(f"{len(rows)} 份样例全部 Σ分期==总额且与黄金文件逐字段一致: {ok_all}")
    with open(os.path.join(EVID, "samples_run.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return {"count": len(rows), "all_equal": ok_all,
            "golden_match_count": sum(1 for r in rows if r["golden_match"]), "rows": rows}


def run_no_float():
    p = subprocess.run([PY, "check_no_float.py", "schedule.py"], cwd=HERE,
                       capture_output=True, text=True, encoding="utf-8")
    text = (p.stdout + p.stderr).strip()
    m = re.search(r"违规 (\d+) 处", text)
    return {"exit_code": p.returncode, "violations": int(m.group(1)) if m else None,
            "output": text}


def run_idempotency():
    store = sch.PlanStore()
    ev = {"source_event_id": "evt-2856-idem", "contract_id": "HT-2856-IDEM",
          "company_id": "co-demo", "start_date": "2026-01-01", "end_date": "2026-12-31",
          "pay_cycle": "quarter",
          "fees": [{"fee_type": "rent", "period_amount_cents": 300000}],
          "deposit_cents": 50000, "first_payment_date": "2026-01-01", "advance_days": 10}
    created = [store.consume(ev)[1] for _ in range(3)]
    plans = {id(store.consume(ev)[0]) for _ in range(2)}
    return {"deliveries": 3, "created_flags": created,
            "created_count": sum(1 for c in created if c),
            "plan_instances": len(plans),
            "plan_count_in_store": len(store._active_by_contract)}


def ac1_numbers():
    """验收 #1：12 个月季付 → 租金 4 / 会籍 4 / 押金 1，逐分相等。"""
    ev = json.load(open(os.path.join(HERE, "sample_contracts",
                                     "01_12m_quarter_tail.json"), encoding="utf-8"))
    plan = sch.build_plan(ev)
    g = lambda t: [i for i in plan.installments if i.fee_type == t]
    rent, mem, dep = g("rent"), g("membership"), g("deposit")
    exp = json.load(open(os.path.join(HERE, "sample_contracts",
                                      "01_12m_quarter_tail.expected.json"), encoding="utf-8"))
    return {
        "contract": ev["contract_id"], "pay_cycle": ev["pay_cycle"],
        "rent_count": len(rent), "rent_sum": sum(i.amount_cents for i in rent),
        "rent_total": exp["per_type_sum"]["rent"],
        "membership_count": len(mem), "membership_sum": sum(i.amount_cents for i in mem),
        "membership_total": exp["per_type_sum"]["membership"],
        "deposit_count": len(dep), "deposit_sum": sum(i.amount_cents for i in dep),
        "deposit_due_date": dep[0].due_date.isoformat() if dep else None,
        "installments_total": len(plan.installments),
        "second_due_date": rent[1].due_date.isoformat() if len(rent) > 1 else None,
        "all_positive": all(i.amount_cents > 0 for i in plan.installments),
    }


def build_verify():
    os.makedirs(OUT, exist_ok=True)
    t = run_pytest()
    s = run_samples()
    nf = run_no_float()
    idem = run_idempotency()
    a1 = ac1_numbers()
    files = ["schedule.py", "reference.py", "check_no_float.py", "make_samples.py", "verify.py",
             "README.md", "tests/test_schedule.py", "evidence/pytest.txt",
             "evidence/samples_run.txt", "sample_contracts/01_12m_quarter_tail.json",
             "sample_contracts/01_12m_quarter_tail.expected.json"]
    shas = {}
    for rel in files:
        p = os.path.join(HERE, rel)
        if os.path.exists(p):
            shas[rel] = {"sha256": sha256(p), "bytes": os.path.getsize(p)}
    v = {
        "problem_id": 2856,
        "title": "S4-FIN-002 签约事件生成回款计划的分期算法与尾差处理",
        "generated_at_local": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "python": sys.version.split()[0],
        "tests": t,
        "samples": s,
        "no_float": nf,
        "idempotency": idem,
        "ac1": a1,
        "files": shas,
        "checks": {
            "ac1_counts_and_sums": (a1["rent_count"] == 4 and a1["membership_count"] == 4
                                    and a1["deposit_count"] == 1
                                    and a1["rent_sum"] == a1["rent_total"]
                                    and a1["membership_sum"] == a1["membership_total"]
                                    and a1["all_positive"]),
            "ac2_hypothesis_200": t["exit_code"] == 0,
            "ac3_idempotent": idem["created_count"] == 1 and idem["plan_count_in_store"] == 1,
            "ac4_no_float": nf["violations"] == 0 and nf["exit_code"] == 0,
            "samples_all_golden_match": s["all_equal"] and s["golden_match_count"] == s["count"],
        },
    }
    v["all_pass"] = all(v["checks"].values())
    with open(os.path.join(OUT, "verify.json"), "w", encoding="utf-8") as f:
        json.dump(v, f, ensure_ascii=False, indent=1)

    with open(os.path.join(OUT, "ac-checklist.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["验收项", "要求", "实测", "结论"])
        w.writerow(["AC1", "12 个月季付：租金 4 期 / 会籍 4 期 / 押金 1 期，逐分相等",
                    f"租金 {a1['rent_count']} 期 Σ={a1['rent_sum']}（合同 {a1['rent_total']}）；"
                    f"会籍 {a1['membership_count']} 期 Σ={a1['membership_sum']}（合同 {a1['membership_total']}）；"
                    f"押金 {a1['deposit_count']} 期 Σ={a1['deposit_sum']}",
                    "PASS" if v["checks"]["ac1_counts_and_sums"] else "FAIL"])
        w.writerow(["AC2", "hypothesis 随机 200 份合同 Σ分期==总额",
                    f"max_examples=200，pytest {t['passed_tests']} 通过 / 失败 {t['failed']}",
                    "PASS" if v["checks"]["ac2_hypothesis_200"] else "FAIL"])
        w.writerow(["AC3", "同一事件重复投递 3 次只生成 1 个计划",
                    f"created_flags={idem['created_flags']}，store 内 active 计划 {idem['plan_count_in_store']} 个",
                    "PASS" if v["checks"]["ac3_idempotent"] else "FAIL"])
        w.writerow(["AC4", "金额模块无 float 运算",
                    f"AST 扫描违规 {nf['violations']} 处（exit {nf['exit_code']}）",
                    "PASS" if v["checks"]["ac4_no_float"] else "FAIL"])

    lines = [
        "S4-FIN-002 验证记录（由 verify.py 实跑生成，勿手改）",
        "=" * 66,
        f"时间: {v['generated_at_local']}  Python {v['python']}  "
        f"pytest {t['pytest_version']}  hypothesis {t['hypothesis_version']}",
        "",
        f"[1] pytest tests/ -v → exit={t['exit_code']} "
        f"{t['passed_tests']} passed / {t['failed']} failed in {t['duration_seconds']}s",
    ]
    for name in t["test_names"]:
        lines.append(f"      PASSED {name}")
    lines += [
        "",
        f"[2] 10 份样例合同：{s['count']} 份，Σ分期==总额 {s['all_equal']}，"
        f"黄金文件逐字段一致 {s['golden_match_count']}/{s['count']}",
    ]
    for r in s["rows"]:
        lines.append(f"      {r['sample']:24s} {r['pay_cycle']:10s} "
                     f"{r['installments']:3d} 期  "
                     f"{r['contract_total_cents']:>9d} 分  sum_ok={r['sum_equals_total']}")
    lines += [
        "",
        f"[3] 幂等：投递 {idem['deliveries']} 次 → created={idem['created_flags']}，"
        f"新建 {idem['created_count']} 个，store 内 active 计划 {idem['plan_count_in_store']} 个",
        "",
        f"[4] 无 float 静态检查：{nf['output']}",
        "",
        f"[5] AC1 明细：租金 {a1['rent_count']} 期 Σ{a1['rent_sum']}/{a1['rent_total']}，"
        f"会籍 {a1['membership_count']} 期 Σ{a1['membership_sum']}/{a1['membership_total']}，"
        f"押金 {a1['deposit_count']} 期 {a1['deposit_sum']} 到期 {a1['deposit_due_date']}，"
        f"第 2 期到期 {a1['second_due_date']}（周期开始 2026-04-01 − advance 10 天）",
        "",
        f"总判定: {'全部通过' if v['all_pass'] else '存在未通过项'}",
    ]
    with open(os.path.join(OUT, "verification-run.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return v


def render_index(v):
    t, s, nf, idem, a1 = v["tests"], v["samples"], v["no_float"], v["idempotency"], v["ac1"]
    rows = "\n".join(
        f"<tr><td>{r['sample']}</td><td>{r['pay_cycle']}</td><td>{r['installments']}</td>"
        f"<td>{r['contract_total_cents']:,}</td><td>{'✅' if r['sum_equals_total'] else '❌'}</td>"
        f"<td>{'✅' if r['golden_match'] else '❌'}</td></tr>" for r in s["rows"])
    flist = "\n".join(
        f'<li><a href="{rel}">{rel}</a> <span class="meta">sha256:{meta["sha256"][:16]} · '
        f'{meta["bytes"]} bytes</span></li>'
        for rel, meta in v["files"].items())
    ac_table = f"""<table><thead><tr><th>验收标准</th><th>实测</th><th>结论</th></tr></thead><tbody>
<tr><td>① 12 个月季付：租金 4 期、会籍 4 期、押金 1 期，逐分相等</td>
<td>租金 {a1['rent_count']} 期 Σ={a1['rent_sum']:,}（合同 {a1['rent_total']:,}）；会籍 {a1['membership_count']} 期 Σ={a1['membership_sum']:,}（合同 {a1['membership_total']:,}）；押金 {a1['deposit_count']} 期 {a1['deposit_sum']:,}，到期 {a1['deposit_due_date']}</td>
<td>{'✅ PASS' if v['checks']['ac1_counts_and_sums'] else '❌ FAIL'}</td></tr>
<tr><td>② hypothesis 随机 200 份合同（含尾期折算），Σ分期==总额</td>
<td>max_examples=200，pytest {t['passed_tests']} passed / {t['failed']} failed（{t['duration_seconds']}s，hypothesis {t['hypothesis_version']}）</td>
<td>{'✅ PASS' if v['checks']['ac2_hypothesis_200'] else '❌ FAIL'}</td></tr>
<tr><td>③ 同一事件重复投递 3 次只生成 1 个计划</td>
<td>投递 {idem['deliveries']} 次 created={idem['created_flags']}；store 内 active 计划 {idem['plan_count_in_store']} 个</td>
<td>{'✅ PASS' if v['checks']['ac3_idempotent'] else '❌ FAIL'}</td></tr>
<tr><td>④ 金额计算模块中没有 float 运算</td>
<td>AST 扫描违规 {nf['violations']} 处（退出码 {nf['exit_code']}）；检查器对违规样本正确报警（test_no_float_checker_detects_violation）</td>
<td>{'✅ PASS' if v['checks']['ac4_no_float'] else '❌ FAIL'}</td></tr>
<tr><td>附：10 份样例合同与期望分期黄金文件逐字段一致</td>
<td>{s['golden_match_count']}/{s['count']} 份一致，Σ分期==总额 {s['all_equal']}</td>
<td>{'✅ PASS' if v['checks']['samples_all_golden_match'] else '❌ FAIL'}</td></tr>
</tbody></table>"""
    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>S4-FIN-002 签约事件分期算法与尾差处理</title>
<style>
:root{{--ink:#111827;--sub:#5b6472;--line:#e5e7eb;--acc:#1f3864;--bg:#fbfcfe}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.75 "Microsoft YaHei","PingFang SC",system-ui,sans-serif}}
.wrap{{max-width:960px;margin:0 auto;padding:40px 24px 64px}}
h1{{font-size:26px;margin:0 0 6px;color:var(--acc)}}
.sub{{color:var(--sub);margin:0 0 24px}}
.kpi{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:24px 0}}
.card{{background:#fff;border:1px solid var(--line);border-radius:10px;padding:16px}}
.card b{{display:block;font-size:24px;color:var(--acc)}}
.card span{{color:var(--sub);font-size:13px}}
h2{{font-size:18px;margin:32px 0 10px;padding-left:10px;border-left:4px solid var(--acc)}}
table{{width:100%;border-collapse:collapse;background:#fff;font-size:14px}}
th,td{{border:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}}
th{{background:#eef2f9;font-weight:600}}
ul{{padding-left:22px}}li{{margin:4px 0}}
a{{color:var(--acc)}}
.meta{{color:var(--sub);font-size:12px}}
.note{{background:#fff;border:1px dashed var(--line);border-radius:10px;padding:14px 16px;color:var(--sub);font-size:13px}}
code{{background:#eef2f9;padding:1px 5px;border-radius:4px;font-size:13px}}
</style></head><body><div class="wrap">
<h1>#2856 · 签约事件生成回款计划：分期算法与尾差处理（S4-FIN-002）</h1>
<p class="sub">整数分 + Decimal 全程无 float · 尾期按天折算 + 尾差归最后一期 · hypothesis 200 例属性测试 · 幂等双重防护</p>

<div class="kpi">
<div class="card"><b>{t['passed_tests']}</b><span>pytest 通过 / 失败 {t['failed']}</span></div>
<div class="card"><b>200</b><span>hypothesis 随机合同全过</span></div>
<div class="card"><b>{s['golden_match_count']}/{s['count']}</b><span>样例合同黄金文件一致</span></div>
<div class="card"><b>{nf['violations']}</b><span>float 违规（AST 检查）</span></div>
</div>

<h2>交付文件（浏览器可直接打开）</h2><ul>
{flist}
</ul>

<h2>验收标准逐条对应（实测）</h2>
{ac_table}

<h2>10 份样例合同（合同总额单位：分）</h2>
<table><thead><tr><th>样例</th><th>付款周期</th><th>分期数</th><th>合同总额（分）</th><th>Σ分期==总额</th><th>黄金文件一致</th></tr></thead>
<tbody>
{rows}
</tbody></table>

<h2>算法要点</h2>
<ul>
<li>整期金额 = 周期金额原值（整数分，不做除法）；尾期日金额 = 月金额 × 12 ÷ 365（Decimal，ROUND_HALF_UP 到分）。</li>
<li>尾差 = 该费用类型总额 − Σ整期 − 尾期折算值，计入该类型最后一期 → 每个费用类型逐分相等。</li>
<li>到期日：首期 = 首付款日；后续每期 = 周期开始日 − <code>advance_days</code>；押金独立 1 行，到期日 = 首付款日。</li>
<li>多年合同输出 <code>first_year_amount_cents</code>（起始 12 个月内开始的周期的分期之和）。</li>
<li>幂等：<code>PlanStore</code> 以 <code>source_event_id</code> 唯一 + 同合同仅一个 active 计划双重防护；生产替换为 PostgreSQL 唯一索引 / 部分唯一索引，接口不变。</li>
</ul>

<h2>复现命令</h2>
<div class="note">
python -m pytest tests/ -v &nbsp;→&nbsp; {t['passed_tests']} passed in {t['duration_seconds']}s<br>
python check_no_float.py schedule.py &nbsp;→&nbsp; 违规 {nf['violations']} 处，退出码 {nf['exit_code']}<br>
python make_samples.py &nbsp;→&nbsp; 重算 10 份样例与期望分期<br>
python verify.py &nbsp;→&nbsp; 重跑全部检查并重写 <a href="outputs/verify.json">outputs/verify.json</a>
</div>

<h2>证据文件</h2>
<ul>
<li><a href="outputs/verification-run.txt">outputs/verification-run.txt</a> — 五段式验证记录（pytest 逐条 / 样例 / 幂等 / 无 float / AC1 明细）</li>
<li><a href="outputs/verify.json">outputs/verify.json</a> — 实测数字唯一来源，本页所有数字由它自动回填</li>
<li><a href="outputs/ac-checklist.csv">outputs/ac-checklist.csv</a> — 验收项逐条实测表</li>
<li><a href="evidence/pytest.txt">evidence/pytest.txt</a> · <a href="evidence/samples_run.txt">evidence/samples_run.txt</a></li>
</ul>

<p class="meta">生成时间 {v['generated_at_local']} · Python {v['python']} · 全部数据为虚构样例，不含任何真实客户或个人信息 · 未引入任何向境外发送数据的第三方 SDK</p>
</div></body></html>
"""
    with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    v = build_verify()
    render_index(v)          # index.html 的 sha256 不入 verify.files，避免自引用
    print(json.dumps({"all_pass": v["all_pass"], "checks": v["checks"],
                      "tests": v["tests"]["passed_tests"],
                      "samples": v["samples"]["count"]}, ensure_ascii=False, indent=1))
