# -*- coding: utf-8 -*-
"""redteam-gen 命令入口。

用法（在仓库根目录）：
  python redteam-gen generate [--seeds 10] [--root .]
  python redteam-gen promote  [--root .]

generate：生成变体 → 写 evals/suites/guardrail.variants.pending/pending.json
promote ：读 pending 目录 → 抽检率达标后并入 evals/suites/guardrail.regression.json
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import redteam as rt  # noqa: E402


def cmd_generate(args):
    seeds = rt.load_seeds(n=args.seeds)
    existing_file = os.path.join(args.root, rt.REGRESSION_FILE)
    existing = []
    if os.path.exists(existing_file):
        existing = json.load(open(existing_file, encoding="utf-8"))
    variants = rt.generate(seeds, existing=existing)
    path = rt.write_pending(variants, root=args.root)
    stats = {}
    for v in variants:
        stats[v["technique"]] = stats.get(v["technique"], 0) + 1
    print(json.dumps({
        "seeds": len(seeds), "variants": len(variants), "dropped": getattr(rt.generate, "last_dropped", 0),
        "per_technique": stats, "pending": os.path.relpath(path, args.root),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_promote(args):
    pending = rt.read_pending(root=args.root)
    if not pending:
        print("pending 为空：先运行 redteam-gen generate", file=sys.stderr)
        return 2
    suite_file = os.path.join(args.root, rt.REGRESSION_FILE)
    suite = json.load(open(suite_file, encoding="utf-8")) if os.path.exists(suite_file) else []
    try:
        merged = rt.promote(pending, suite, root=args.root)
    except ValueError as e:
        print("拒绝并入：%s" % e, file=sys.stderr)
        return 1
    print(json.dumps({"promoted": len(pending), "suite_total": len(merged),
                      "regression": rt.REGRESSION_FILE}, ensure_ascii=False, indent=2))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="redteam-gen", description="#2052 红队变体生成器")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="生成变体并写入 pending 目录")
    g.add_argument("--seeds", type=int, default=10)
    g.add_argument("--root", default=".")
    g.set_defaults(func=cmd_generate)
    p = sub.add_parser("promote", help="把 pending 并入回归集（需抽检率 >= 10%）")
    p.add_argument("--root", default=".")
    p.set_defaults(func=cmd_promote)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
