#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构造虚构测试数据集（干净集 + 6 类已知差异集 + 性能集 1000 企业/5000 联系人）。

全部数据为虚构：企业名 FICT-xxx、手机号 139 开头假号段、信用代码 91FICT 开头。
"""
import csv
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def w(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f)
        wr.writerow(header)
        wr.writerows(rows)


def make_dataset(n_companies, n_contacts, site="site-A", seed=42):
    rnd = random.Random(seed)
    companies, contacts, rels, tags, tlinks = [], [], [], [], []
    for i in range(n_companies):
        companies.append([f"C{i:06d}", site, f"FICT企业{i}", f"91FICT{i:012d}",
                          rnd.choice(["软件", "咨询", "零售"]), rnd.choice(["vip", "normal"]),
                          rnd.choice(["active", "probation"]), ""])
    for i in range(n_contacts):
        contacts.append([f"P{i:06d}", site, f"联系人{i}",
                         f"139{rnd.randrange(10**8):08d}", f"职位{i}"])
        # 每个联系人至少关联一家企业
        rels.append([f"R{i:06d}", site, f"P{i:06d}", f"C{rnd.randrange(n_companies):06d}",
                     rnd.choice(["member", "admin"])])
    for i in range(20):
        tags.append([f"T{i:03d}", site, f"标签{i}"])
        tlinks.append([f"L{i:03d}", site, f"T{i % 20:03d}", "company",
                       f"C{rnd.randrange(n_companies):06d}"])
    return companies, contacts, rels, tags, tlinks


def write_set(dst, companies, contacts, rels, tags, tlinks, mapping=None, with_target_id=True):
    os.makedirs(dst, exist_ok=True)
    w(os.path.join(dst, "companies.csv"),
      ["source_id", "site_id", "name", "credit_code", "industry", "member_level",
       "onsite_status", "deleted_at"], companies)
    w(os.path.join(dst, "contacts.csv"),
      ["source_id", "site_id", "name", "phone", "position"], contacts)
    w(os.path.join(dst, "contact_company.csv"),
      ["source_id", "site_id", "contact_id", "company_id", "relation_type"], rels)
    w(os.path.join(dst, "tags.csv"), ["source_id", "site_id", "name"], tags)
    w(os.path.join(dst, "tag_objects.csv"),
      ["source_id", "site_id", "tag_id", "object_type", "object_id"], tlinks)
    if mapping is not None:
        w(os.path.join(dst, "mapping.csv"), ["source_id", "target_id"], mapping)


def target_rows(rows, new_id=None):
    """目标侧行：默认 target_id=source_id（无映射表直连场景）。"""
    return rows


def build_clean(dst):
    c, p, r, t, l = make_dataset(30, 80)
    write_set(dst, c, p, r, t, l)


def build_six_diffs(dst):
    """构造 6 类已知差异：
    D1 缺失（missing）：源 1 条企业在映射/目标中缺失
    D2 字段不一致（field）：1 家企业名称不一致 + 1 条手机号格式不同（应被标准化吸收→改用真实差异：行业不同）
    D3 重复映射（duplicate）：1 个 source_id 映射到 2 个 target
    D4 多对一（many_to_one）：2 个 source_id 映射到同一 target
    D5 无关联企业（orphan_contact）：1 个联系人无企业关联
    D6 信用代码重复（credit_code_conflict）：2 家未删除企业同信用代码
    """
    c, p, r, t, l = make_dataset(30, 80)
    # 预处理：把指向 C000028/C000029 的关联改指 C000000（双侧同步），
    # 避免 D1/D4 的映射异常产生连锁字段噪声
    for x in (r,):
        for row in x:
            if row[3] in ("C000028", "C000029"):
                row[3] = "C000000"
    mapping = [[x[0], x[0]] for x in c + p + r + t + l]

    # 目标侧副本
    tc = [list(x) for x in c]
    tp = [list(x) for x in p]
    tr = [list(x) for x in r]
    tt = [list(x) for x in t]
    tl = [list(x) for x in l]

    # D1 缺失：删除目标侧最后一家企业，并从映射中删除
    gone = tc[-1][0]
    tc.pop()
    mapping = [m for m in mapping if m[1] != gone]

    # D2 字段不一致：目标侧第一家企业行业不同；第 6 个联系人姓名不同；
    # 第 8 个联系人手机号不同（用于验证明细掩码）
    tc[0][4] = "制造"
    tp[5][2] = "联系人五号改"
    tp[7][3] = "13800001111"

    # D3 重复映射：给第一个联系人额外映射到第二个联系人
    mapping.append([tp[0][0], tp[1][0]])

    # D4 多对一：给 C000028 追加映射到 C000027（2 源 → 1 目标）
    mapping.append(["C000028", "C000027"])

    # D5 无关联企业：源侧删除最后一个联系人的关联（该联系人失去唯一关联）
    r.pop()

    # D6 信用代码重复：源侧第二家企业与第一家同信用代码（均为未删除，双侧同步改，
    # 只触发业务规则差异、不混入字段差异）
    c[1][3] = c[0][3]
    tc[1][3] = tc[0][3]

    write_set(dst, c, p, r, t, l, mapping=mapping)
    write_set(os.path.join(dst, "_target"), tc, tp, tr, tt, tl, mapping=None)
    print("已知差异清单: D1 missing=%s D2 field=2条 D3 duplicate=%s D4 many_to_one=C000027<-C000028 D5 orphan=1 D6 credit=1"
          % (gone, tp[0][0]))


def build_perf(dst):
    c, p, r, t, l = make_dataset(1000, 5000)
    write_set(dst, c, p, r, t, l)
    write_set(os.path.join(dst, "_target"), c, p, r, t, l, mapping=None)


if __name__ == "__main__":
    build_clean(os.path.join(HERE, "clean"))
    build_six_diffs(os.path.join(HERE, "six_diffs"))
    if "--with-perf" in sys.argv:
        build_perf(os.path.join(HERE, "perf"))
    print("fixtures ready")
