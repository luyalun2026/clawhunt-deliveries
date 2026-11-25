# -*- coding: utf-8 -*-
"""生成互动卡片静态页（数字由 stub 逻辑实跑导出，非手写）+ 无头浏览器截图。"""
import json
import os
import sqlite3
import subprocess
import sys
import datetime as dt
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from loop4_common import MEMBER_U1, ENT_A, ENT_B, INTERACTION_TYPES
import seed as seed_mod

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = seed_mod.DB_PATH


def compute_counts():
    """直接按 stub 同口径实跑计算卡片 6 项计数。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    today = dt.date.today()
    lo = today.replace(day=1).isoformat() + "T00:00:00"
    nxt = (today.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    hi = nxt.isoformat() + "T00:00:00"
    row = cur.execute("SELECT enterprise_id FROM members WHERE id=? AND deleted_at IS NULL",
                      (MEMBER_U1["id"],)).fetchone()
    ent = row["enterprise_id"]
    cnt = defaultdict(int)
    esc = 0
    for r in cur.execute(
            "SELECT type, escalated FROM interactions WHERE member_id=? AND type IN (%s) "
            "AND deleted_at IS NULL AND occurred_at >= ? AND occurred_at < ?" % ",".join("?" * len(INTERACTION_TYPES)),
            [MEMBER_U1["id"]] + INTERACTION_TYPES + [lo, hi]):
        cnt[r["type"]] += 1
        esc += r["escalated"]
    counts = {"认证联系人数": cnt["auth"], "发布需求数": cnt["demand"],
              "报名数": cnt["signup"], "签到数": cnt["checkin"],
              "提问数": cnt["ask"], "转人工数": esc}
    active = {r["enterprise_id"] for r in cur.execute(
        "SELECT DISTINCT m.enterprise_id FROM interactions i JOIN members m ON m.id=i.member_id "
        "WHERE i.type IN (%s) AND i.deleted_at IS NULL AND m.deleted_at IS NULL "
        "AND i.occurred_at >= ? AND i.occurred_at < ?" % ",".join("?" * len(INTERACTION_TYPES)),
        INTERACTION_TYPES + [lo, hi])}
    conn.close()
    return counts, ent, active


def render_card(counts, ent, active):
    cells = "".join(
        f'<div class="cell"><div class="num">{v}</div><div class="lbl">{k}</div></div>'
        for k, v in counts.items())
    mau = f'<div class="mau">月活分子包含企业 <b>{ent}</b>（有有效互动）｜排除企业 <b>{ENT_B["id"]}</b>（仅浏览）</div>'
    html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<style>
body{{font-family:'Microsoft YaHei',sans-serif;background:#f5f7fa;margin:0;padding:24px}}
.card{{background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.08);padding:24px;max-width:640px}}
h2{{margin:0 0 4px;font-size:20px}} .sub{{color:#888;font-size:12px;margin-bottom:16px}}
.grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}}
.cell{{background:#f0f5ff;border-radius:8px;padding:12px 4px;text-align:center}}
.num{{font-size:22px;font-weight:700;color:#1a56db}} .lbl{{font-size:11px;color:#666;margin-top:4px}}
.mau{{margin-top:16px;font-size:12px;color:#555;background:#f2fbf4;border-radius:8px;padding:8px}}
</style></head><body><div class="card">
<h2>小程序互动 · 企业详情</h2><div class="sub">闭环四 · 数据来源 stub（source=mini，当月）</div>
<div class="grid">{cells}</div>{mau}</div></body></html>"""
    path = os.path.join(HERE, "card.html")
    open(path, "w", encoding="utf-8").write(html)
    return path


def screenshot(path):
    out = os.path.join(HERE, "screenshots", "interaction_card.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if not os.path.exists(edge):
        edge = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    subprocess.run([edge, "--headless=new", "--disable-gpu",
                    f"--user-data-dir={os.path.join(HERE, '.edge_tmp')}",
                    "--window-size=720,360",
                    f"--screenshot={out}", "file:///" + path.replace("\\", "/")],
                   capture_output=True, timeout=60)
    return out if os.path.exists(out) else None


if __name__ == "__main__":
    counts, ent, active = compute_counts()
    card = render_card(counts, ent, active)
    # 自检：卡片 HTML 中 6 项计数文本与实跑结果一致
    for k, v in counts.items():
        assert f">{v}</div><div class=\"lbl\">{k}</div>" in open(card, encoding="utf-8").read(), k
    assert ent in active
    shot = screenshot(card)
    json.dump({"counts": counts, "enterprise": ent, "active_enterprises": sorted(active),
               "card_html": os.path.basename(card),
               "screenshot": os.path.basename(shot) if shot else None},
              open(os.path.join(HERE, "artifacts", "card_data.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("counts:", counts)
    print("screenshot:", shot)
