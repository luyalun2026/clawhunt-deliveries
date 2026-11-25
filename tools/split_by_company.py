# -*- coding: utf-8 -*-
"""split_by_company.py — 按企业分组的训练/验证切分（防同企业跨集泄漏）。"""
from __future__ import annotations
import random


def group_split(rows: list[dict], ratio: float = 0.7, seed: int = 42):
    """rows: churn_label 行；返回 (train_rows, valid_rows)。

    以 company_pid 为分组单位整体切分，同一企业的全部快照只进一个集合。
    """
    pids = sorted({r["company_pid"] for r in rows})
    rng = random.Random(seed)
    rng.shuffle(pids)
    n_train = max(1, int(len(pids) * ratio))
    train_pids = set(pids[:n_train])
    train = [r for r in rows if r["company_pid"] in train_pids]
    valid = [r for r in rows if r["company_pid"] not in train_pids]
    return train, valid


if __name__ == "__main__":
    import argparse, json
    from build_churn_labels import build_labels
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--ratio", type=float, default=0.7)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    rows = build_labels(json.load(open(a.input, encoding="utf-8")))
    tr, va = group_split(rows, a.ratio, a.seed)
    print(f"companies={len({r['company_pid'] for r in rows})} train_rows={len(tr)} valid_rows={len(va)}")
