#!/usr/bin/env python3
"""validate_tags.py — 标签体系校验：必填非空、定义 ≤50 字、正例 2 条反例 1 条齐全。

失败退出码 1，成功打印「N/M 全通过」并退出 0。
"""
from __future__ import annotations
import argparse, sys

import yaml


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", required=True)
    args = ap.parse_args()

    data = yaml.safe_load(open(args.seed, encoding="utf-8"))
    fails = []
    total = 0
    for dim, tags in data.items():
        for t in tags:
            total += 1
            tag_id = f"{dim}/{t.get('code', '<no-code>')}"
            if not t.get("code"):
                fails.append(f"{tag_id}: 缺 code")
            if not t.get("name"):
                fails.append(f"{tag_id}: 缺 name")
            d = t.get("definition", "")
            if not d:
                fails.append(f"{tag_id}: 缺定义")
            elif len(d) > 50:
                fails.append(f"{tag_id}: 定义 {len(d)} 字 > 50")
            pos = t.get("positives", [])
            if len(pos) != 2:
                fails.append(f"{tag_id}: 正例 {len(pos)} 条 != 2")
            if not t.get("negative"):
                fails.append(f"{tag_id}: 缺反例")

    if fails:
        for f in fails:
            print("FAIL", f)
        print(f"校验失败 {len(fails)} 项 / 共 {total} 标签")
        return 1
    print(f"{total}/{total} 标签校验全通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
