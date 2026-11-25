#!/usr/bin/env python3
"""sop-lint <文件或目录> — SOP 模板静态检查，CI 可用。

退出码：0 全绿；1 有错误；2 用法错误。
"""
from __future__ import annotations
import json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import sop_core


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("用法: sop-lint <文件或目录> [--catalogs <catalogs.json>]", file=sys.stderr)
        return 2

    targets = []
    catalogs = None
    args = list(argv[1:])
    if "--catalogs" in args:
        i = args.index("--catalogs")
        catalogs = sop_core.load_catalogs(args[i + 1])
        del args[i:i + 2]
    target = args[0]

    if os.path.isdir(target):
        for name in sorted(os.listdir(target)):
            if name.endswith(".json"):
                targets.append(os.path.join(target, name))
    else:
        targets.append(target)

    if not targets:
        print("无 .json 模板文件")
        return 0

    if catalogs is None:
        catalogs = sop_core.load_catalogs()

    total_errors = 0
    for path in targets:
        try:
            tpl = json.load(open(path, encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"[FAIL] {path}: JSON 解析失败 {e}")
            total_errors += 1
            continue
        errors = sop_core.lint_template(tpl, catalogs)
        if errors:
            total_errors += len(errors)
            for e in errors:
                print(f"[FAIL] {path} [{e['rule']}] {e['path']}: {e['message']}")
        else:
            print(f"[OK]   {path}")

    print(f"共 {total_errors} 个错误 / {len(targets)} 个文件")
    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
