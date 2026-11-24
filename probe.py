# -*- coding: utf-8 -*-
"""运行期采集：20 轮双线程竞争、8 路并发、到期释放与身份泄露检查（数字全部实测）。"""
import json
import os
import tempfile
import time
from datetime import timedelta

from app.attribution import AttributionService
from app.crm_stub import CrmStub
from app.db import init_db
from harness import BASE, make_report, race

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")


def main():
    os.makedirs(OUT, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="attr-probe-")
    db_path = os.path.join(tmp, "probe.db")
    init_db(db_path)
    service = AttributionService(db_path, crm=CrmStub(), salt="probe-salt")

    rounds, wins, dups, errors = 20, 0, 0, 0
    durations = []
    for index in range(rounds):
        tag = "%03d" % index
        reports = [
            make_report("CH-001", "探针虚构企业%s有限公司" % tag, "91420100MA4P%s0001" % tag,
                        "1380013%04d" % index),
            make_report("CH-002", "探针虚构企业%s有限公司" % tag, "91420100MA4P%s0001" % tag,
                        "1390013%04d" % index),
        ]
        started = time.perf_counter()
        results = race(service, reports)
        durations.append((time.perf_counter() - started) * 1000)
        for result in results:
            if result["status"] == "accepted":
                wins += 1
            elif result["status"] == "rejected_duplicate":
                dups += 1
            else:
                errors += 1

    eight = [make_report("CH-001", "八路虚构企业有限公司", "91420100MA4P8888X1",
                         "1370013%04d" % i) for i in range(8)]
    eight_results = race(service, eight)

    # 保护期与身份隔离用独立库，避免并发批次的历史报备干扰到期计数
    db2 = os.path.join(tmp, "probe-lifecycle.db")
    init_db(db2)
    lifecycle = AttributionService(db2, crm=CrmStub(), salt="probe-salt")

    accepted = lifecycle.decide(make_report("CH-001", "到期虚构企业有限公司",
                                            "91420100MA4P9999X1", "13600136000"), now=BASE)
    keys_before = len(lifecycle.active_keys(accepted["report_id"]))
    expired = lifecycle.expire_due(now=BASE + timedelta(days=91))
    keys_after = len(lifecycle.active_keys(accepted["report_id"]))
    reentry = lifecycle.decide(make_report("CH-002", "到期虚构企业有限公司",
                                           "91420100MA4P9999X1", "13600136001"),
                               now=BASE + timedelta(days=92))

    first = lifecycle.decide(make_report("CH-001", "泄露检查虚构有限公司",
                                         "91420100MA4PL00001", "13500135000"), now=BASE)
    dup_result = lifecycle.decide(make_report("CH-002", "泄露检查另一名称有限公司",
                                              "91420100MA4PL00001", "13500135001"), now=BASE)
    blob = json.dumps(dup_result, ensure_ascii=False)
    leaked = [token for token in ("CH-001", "虚构渠道甲", "13500135000") if token in blob]

    metrics = {
        "concurrency_rounds": rounds,
        "accepted_wins": wins,
        "duplicate_losers": dups,
        "unexpected_results": errors,
        "round_ms_max": round(max(durations), 1),
        "round_ms_avg": round(sum(durations) / len(durations), 1),
        "eight_way_winners": [r["status"] for r in eight_results].count("accepted"),
        "eight_way_duplicates": [r["status"] for r in eight_results].count("rejected_duplicate"),
        "keys_before_expiry": keys_before,
        "keys_after_expiry": keys_after,
        "expired_count": expired["expired"],
        "reentry_status": reentry["status"],
        "identity_leaks": leaked,
        "first_rule_version": first["rule_version"],
        "first_protection_until": first["protection_until"],
    }

    lines = [
        "# 并发与保护期实测（自动采集）", "",
        "| 指标 | 实测值 |", "|---|---|",
        "| 双线程竞争轮数 | %d |" % metrics["concurrency_rounds"],
        "| 每轮 accepted 数（合计） | %d（每轮恰 1） |" % metrics["accepted_wins"],
        "| 每轮 rejected_duplicate 数（合计） | %d |" % metrics["duplicate_losers"],
        "| 非预期结果（异常/其他状态） | %d |" % metrics["unexpected_results"],
        "| 单轮耗时 平均 / 最大 | %.1f ms / %.1f ms |" % (metrics["round_ms_avg"], metrics["round_ms_max"]),
        "| 8 路并发：accepted / duplicate | %d / %d |" % (
            metrics["eight_way_winners"], metrics["eight_way_duplicates"]),
        "| 到期前活跃 keys | %d |" % metrics["keys_before_expiry"],
        "| 到期后活跃 keys | %d |" % metrics["keys_after_expiry"],
        "| 每日任务置 expired 数 | %d |" % metrics["expired_count"],
        "| 到期后新报备状态 | %s |" % metrics["reentry_status"],
        "| 重复拒绝中泄露的首单身份字段 | %d（%s） |" % (len(leaked), "、".join(leaked) or "无"),
        "| 首单规则版本 / 保护期至 | %s / %s |" % (
            metrics["first_rule_version"], metrics["first_protection_until"]),
        "",
    ]
    with open(os.path.join(OUT, "concurrency-report.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    with open(os.path.join(OUT, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    print(json.dumps(metrics, ensure_ascii=False))


if __name__ == "__main__":
    main()
