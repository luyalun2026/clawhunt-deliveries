#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""会员主数据迁移核对脚本（S4-GO-029）。

四层核对流水线：
  L1 行数核对   —— 按对象类型 / site_id / 状态（有效、软删除）分组计数对照
  L2 主键映射   —— source_id → 新 UUID 唯一性：missing / duplicate / many_to_one
  L3 字段级核对 —— 标准化后逐字段比对，差异按字段汇总，明细 CSV 手机号掩码
  L4 业务规则   —— 信用代码唯一性、联系人必须关联企业、软删除不计有效数

用法：
  python scripts/reconcile_members.py --source <源CSV目录> --target <目标CSV目录> \
      [--mapping <映射表.csv>] [--site <site_id>] [--sample N] [--out <输出目录>]

约定（与工单一致）：
  - 源侧为迁移前导出的 CSV；目标侧默认同样式 CSV（迁移后导出，含映射后 UUID），
    生产对接 PostgreSQL 时用 --db "$DATABASE_URL"（psycopg 只读连接，适配器见 README）。
  - 金额/手机号等敏感字段在明细中掩码；本脚本只读，不写任何数据。
  - 差异为 0 → 退出码 0；存在差异 → 1；参数/文件错误 → 2。
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

# ---------------------------------------------------------------- 对象与字段

OBJECTS = {
    "companies": {
        "file": "companies.csv",
        "key": "source_id",
        "fields": ["name", "credit_code", "industry", "member_level", "onsite_status"],
        "phone": None,
    },
    "contacts": {
        "file": "contacts.csv",
        "key": "source_id",
        "fields": ["name", "phone", "position"],
        "phone": "phone",
    },
    "contact_company": {
        "file": "contact_company.csv",
        "key": "source_id",
        "fields": ["contact_id", "company_id", "relation_type"],
        "phone": None,
        "ref_fields": {"company_id": "name"},  # 所属企业按目标名称比对
    },
    "tags": {
        "file": "tags.csv",
        "key": "source_id",
        "fields": ["name"],
        "phone": None,
    },
    "tag_objects": {
        "file": "tag_objects.csv",
        "key": "source_id",
        "fields": ["tag_id", "object_type", "object_id"],
        "phone": None,
    },
}

CREDIT_CODE_FIELD = "credit_code"

# ---------------------------------------------------------------- 标准化规则

FULLWIDTH_EXTRA = {
    0xFF08: "(", 0xFF09: ")", 0x3010: "[", 0x3011: "]",
    0xFF0C: ",", 0xFF1B: ";", 0xFF1A: ":", 0xFF01: "!", 0xFF1F: "?",
    0x201C: '"', 0x201D: '"', 0x2018: "'", 0x2019: "'",
    0x2014: "-", 0xFF0D: "-", 0xFF05: "%",
}


def normalize_text(v: str | None) -> str:
    """R1 去首尾空格 + R2 全角转半角（NFKC 兜底 + 常用标点映射）。"""
    if v is None:
        return ""
    s = str(v).strip()
    s = unicodedata.normalize("NFKC", s)
    return s.translate(FULLWIDTH_EXTRA).strip()


def normalize_phone(v: str | None) -> str:
    """R3 手机号标准化：去 +86 / 0086 国家码，保留 11 位主体，仅数字。"""
    if v is None:
        return ""
    s = normalize_text(v)
    digits = "".join(c for c in s if c.isdigit())
    for cc in ("0086", "86"):
        if digits.startswith(cc) and len(digits) > 11:
            digits = digits[len(cc):]
    return digits


def mask_phone(v: str | None) -> str:
    p = normalize_phone(v)
    if len(p) == 11:
        return p[:3] + "****" + p[7:]
    return p or ""


# ---------------------------------------------------------------- 数据读取


def read_csv_dir(path: str, site: str | None = None, sample: int | None = None):
    """读取一个目录下的全部对象 CSV，返回 {object: {source_id: rowdict}}。

    若目录不存在或 companies.csv 缺失 → 抛 UsageError（退出码 2）。
    """
    if not os.path.isdir(path):
        raise UsageError(f"目录不存在: {path}")
    main_file = os.path.join(path, OBJECTS["companies"]["file"])
    if not os.path.exists(main_file):
        raise UsageError(f"缺少 {OBJECTS['companies']['file']}: {path}")
    data: dict[str, dict[str, dict]] = {}
    for obj, spec in OBJECTS.items():
        fp = os.path.join(path, spec["file"])
        rows: dict[str, dict] = {}
        if os.path.exists(fp):
            # 支持 UTF-8 与 GBK：先尝试 utf-8-sig，失败回退 gbk
            try:
                fh = open(fp, newline="", encoding="utf-8-sig")
                fh.readline()
                fh.seek(0)
            except UnicodeDecodeError:
                fh = open(fp, newline="", encoding="gbk")
            with fh as f:
                for i, row in enumerate(csv.DictReader(f)):
                    if sample is not None and i >= sample:
                        break
                    if site and row.get("site_id") and row["site_id"] != site:
                        continue
                    k = row.get(spec["key"]) or f"__row{i}"
                    rows[k] = row
        data[obj] = rows
    return data


class UsageError(Exception):
    pass


# ---------------------------------------------------------------- 差异容器


@dataclass
class Diff:
    category: str      # missing / duplicate / many_to_one / field / credit_code_conflict / orphan_contact / count
    object: str
    source_id: str = ""
    field_name: str = ""
    detail: str = ""


@dataclass
class Report:
    diffs: list[Diff] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def add(self, **kw):
        self.diffs.append(Diff(**kw))

    def has_diff(self) -> bool:
        return bool(self.diffs)


# ---------------------------------------------------------------- 四层核对


def check_counts(src, dst, rep: Report):
    """L1 行数：按对象 / site_id / 状态分组对照。"""
    for obj in OBJECTS:
        for label, side in (("src", src), ("dst", dst)):
            by_site = defaultdict(int)
            by_status = {"active": 0, "soft_deleted": 0}
            for r in side[obj].values():
                by_site[r.get("site_id") or "-"] += 1
                if (r.get("deleted_at") or "").strip():
                    by_status["soft_deleted"] += 1
                else:
                    by_status["active"] += 1
            rep.stats[f"count_{label}_{obj}"] = {
                "total": len(side[obj]),
                "by_site": dict(by_site),
                "by_status": by_status,
            }
        s, d = src[obj], dst[obj]
        if len(s) != len(d):
            rep.add(category="count", object=obj,
                    detail=f"行数不一致 src={len(s)} dst={len(d)}")


def check_mapping(src, dst, mapping, rep: Report):
    """L2 主键映射：missing / duplicate / many_to_one（仅对源侧存在的记录）。"""
    m: dict[str, list[str]] = defaultdict(list)
    for row in mapping:
        m[row["source_id"]].append(row["target_id"])
    # duplicate：同一 source_id 映射到多个 target
    for sid, tids in m.items():
        if len(tids) > 1:
            rep.add(category="duplicate", object="mapping", source_id=sid,
                    detail=f"映射到 {len(tids)} 个目标: {','.join(tids)}")
    # many_to_one：多个 source 指向同一 target
    rev = defaultdict(list)
    for sid, tids in m.items():
        for t in tids:
            rev[t].append(sid)
    for t, sids in rev.items():
        if len(sids) > 1:
            rep.add(category="many_to_one", object="mapping", source_id=",".join(sids),
                    detail=f"共同指向目标 {t}")
    # missing：源侧记录没有映射
    for obj in OBJECTS:
        for sid in src[obj]:
            if sid not in m:
                rep.add(category="missing", object=obj, source_id=sid,
                        detail="映射表中无 source_id")


def check_fields(src, dst, mapping, rep: Report, ref_names: dict):
    """L3 字段级：标准化后逐字段比对，差异按字段汇总；手机号明细掩码。"""
    m = {row["source_id"]: row["target_id"] for row in mapping if len(
        [x for x in mapping if x["source_id"] == row["source_id"]]) == 1}
    dst_by_id = {}
    for obj in OBJECTS:
        dst_by_id[obj] = {r.get("target_id") or k: r for k, r in dst[obj].items()}
    field_hits = defaultdict(int)
    for obj, spec in OBJECTS.items():
        phone_f = spec["phone"]
        for sid, srow in src[obj].items():
            tid = m.get(sid)
            if tid is None:
                continue  # missing 已在 L2 记
            drow = dst_by_id[obj].get(tid)
            if drow is None:
                rep.add(category="missing", object=obj, source_id=sid,
                        detail=f"映射目标 {tid} 在目标侧不存在")
                continue
            for f in spec["fields"]:
                if f == "company_id":  # 所属企业：双侧按各自企业表解析名称后比对
                    sval = company_name(src, srow.get("company_id"))
                    dval = company_name(dst, m.get(srow.get("company_id")))
                    if normalize_text(sval) != normalize_text(dval):
                        field_hits[f] += 1
                        rep.add(category="field", object=obj, source_id=sid,
                                field_name="company_name",
                                detail=f"所属企业 src={sval!r} dst={dval!r}")
                    continue
                sval, dval = srow.get(f), drow.get(f)
                norm = normalize_phone if f == phone_f else normalize_text
                if norm(sval) != norm(dval):
                    field_hits[f] += 1
                    shown_s, shown_d = sval or "", dval or ""
                    if f == phone_f:
                        shown_s, shown_d = mask_phone(shown_s), mask_phone(shown_d)
                    rep.add(category="field", object=obj, source_id=sid,
                            field_name=f,
                            detail=f"标准化前 src={shown_s!r} dst={shown_d!r}")
    rep.stats["field_diff_summary"] = dict(field_hits)


def company_name(side, cid):
    if not cid:
        return ""
    row = side["companies"].get(cid)
    if row is None:
        # 目标侧行键可能是 target_id
        for r in side["companies"].values():
            if r.get("source_id") == cid:
                return r.get("name") or ""
        return ""
    return row.get("name") or ""


def check_rules(src, rep: Report):
    """L4 业务规则。"""
    # 同一信用代码对应多个未删除企业
    by_cc = defaultdict(list)
    for r in src["companies"].values():
        if (r.get("deleted_at") or "").strip():
            continue
        cc = normalize_text(r.get(CREDIT_CODE_FIELD))
        if cc:
            by_cc[cc].append(r.get("source_id"))
    for cc, ids in by_cc.items():
        if len(ids) > 1:
            rep.add(category="credit_code_conflict", object="companies",
                    source_id=",".join(ids), detail=f"信用代码 {cc} 对应 {len(ids)} 家未删除企业")
    # 联系人必须关联至少 1 家企业
    linked = {r.get("contact_id") for r in src["contact_company"].values()}
    for cid, r in src["contacts"].items():
        if (r.get("deleted_at") or "").strip():
            continue
        if cid not in linked:
            rep.add(category="orphan_contact", object="contacts", source_id=cid,
                    detail="未关联任何企业")


# ---------------------------------------------------------------- 输出


def write_report(rep: Report, out_dir: str, args) -> tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    md_path = os.path.join(out_dir, "diff_report.md")
    csv_path = os.path.join(out_dir, "diff_detail.csv")
    by_cat = defaultdict(int)
    for d in rep.diffs:
        by_cat[d.category] += 1
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 会员主数据迁移核对报告\n\n")
        f.write(f"- 生成时间: {datetime.now().isoformat(timespec='seconds')}\n")
        f.write(f"- 源目录: {args.source}\n- 目标: {args.target or args.db or '-'}\n")
        if args.site:
            f.write(f"- 限定站点: {args.site}\n")
        if args.sample:
            f.write(f"- 抽样: 每对象前 {args.sample} 条（sampled）\n")
        f.write(f"- 差异总数: {len(rep.diffs)}  退出码: {'0' if not rep.diffs else '1'}\n\n")
        f.write("## 差异汇总\n\n| 类别 | 数量 |\n|---|---|\n")
        for c in ("count", "missing", "duplicate", "many_to_one", "field",
                  "credit_code_conflict", "orphan_contact"):
            f.write(f"| {c} | {by_cat.get(c, 0)} |\n")
        f.write("\n## 行数统计\n\n```json\n")
        import json as _json
        f.write(_json.dumps({k: v for k, v in rep.stats.items()
                             if k.startswith("count_")}, ensure_ascii=False, indent=1))
        f.write("\n```\n\n## 字段差异汇总\n\n")
        fs = rep.stats.get("field_diff_summary") or {}
        if fs:
            f.write("| 字段 | 差异数 |\n|---|---|\n")
            for k, v in sorted(fs.items(), key=lambda x: -x[1]):
                f.write(f"| {k} | {v} |\n")
        else:
            f.write("无字段级差异。\n")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category", "object", "source_id", "field", "detail"])
        for d in rep.diffs:
            w.writerow([d.category, d.object, d.source_id, d.field_name, d.detail])
    return md_path, csv_path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="会员主数据迁移核对")
    ap.add_argument("--source", required=True, help="源数据目录（迁移前 CSV 导出）")
    ap.add_argument("--target", help="目标数据目录（迁移后 CSV 导出，含 target_id）")
    ap.add_argument("--db", help="目标 PostgreSQL 连接串（环境变量 DATABASE_URL 优先）")
    ap.add_argument("--mapping", help="映射表 CSV（source_id,target_id），默认取 target 目录 mapping.csv")
    ap.add_argument("--site", help="限定站点 site_id")
    ap.add_argument("--sample", type=int, help="每对象只核对前 N 条")
    ap.add_argument("--out", default="out", help="报告输出目录")
    args = ap.parse_args(argv)

    try:
        src = read_csv_dir(args.source, args.site, args.sample)
        dst = read_csv_dir(args.target, args.site, args.sample) if args.target else None
    except UsageError as e:
        print(f"[USAGE ERROR] {e}", file=sys.stderr)
        return 2
    if dst is None:
        print("[USAGE ERROR] 需要 --target 或 --db（当前环境优先 CSV 通道）", file=sys.stderr)
        return 2

    mp = args.mapping or os.path.join(args.target, "mapping.csv")
    mapping = []
    if os.path.exists(mp):
        with open(mp, newline="", encoding="utf-8-sig") as f:
            mapping = [r for r in csv.DictReader(f)]
    else:
        # 无映射表时按 source_id == target_id 直连（演示/干净集场景）
        for obj in OBJECTS:
            for k in src[obj]:
                mapping.append({"source_id": k, "target_id": k})

    # ref_names：企业名称表（供 contact_company 的「所属企业」比对）
    ref_names = {}
    for cid, r in src["contact_company"].items():
        ref_names[cid] = normalize_text(
            next((c.get("name") for c in src["companies"].values()
                  if c.get("source_id") == r.get("company_id")), ""))

    rep = Report()
    check_counts(src, dst, rep)
    check_mapping(src, dst, mapping, rep)
    check_fields(src, dst, mapping, rep, ref_names)
    check_rules(src, rep)

    md_path, csv_path = write_report(rep, args.out, args)
    print(f"报告: {md_path}\n明细: {csv_path}")
    print(f"差异总数: {len(rep.diffs)} -> 退出码 {1 if rep.diffs else 0}")
    return 1 if rep.diffs else 0


if __name__ == "__main__":
    sys.exit(main())
