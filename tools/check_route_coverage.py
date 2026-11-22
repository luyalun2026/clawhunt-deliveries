# -*- coding: utf-8 -*-
"""覆盖率门禁：新增未纳入测试的 /api/sales/ 路由时套件必须失败。

用法：
    python -m pytest tests              # 门禁作为用例生效
    python tools/check_route_coverage.py  # 单独执行，违规 exit 1（供 CI 前置检查）
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app  # noqa: E402
from tests.coverage import COVERED  # noqa: E402
from tests.helpers import sales_routes  # noqa: E402


def violations(app, covered=COVERED):
    routes = set(sales_routes(app))
    return sorted(routes - set(covered)), sorted(set(covered) - routes)


def enforce(app, covered=COVERED):
    missing, stale = violations(app, covered)
    if missing or stale:
        parts = []
        if missing:
            parts.append("未纳入测试的路由: %s" % json.dumps(
                ["%s %s" % r for r in missing], ensure_ascii=False))
        if stale:
            parts.append("登记表多余条目: %s" % json.dumps(
                ["%s %s" % r for r in stale], ensure_ascii=False))
        raise AssertionError("；".join(parts))


def main():
    app = create_app()
    routes = sales_routes(app)
    missing, stale = violations(app)
    print("OpenAPI 枚举 /api/sales/ 路由 %d 条，登记表 %d 条" % (len(routes), len(COVERED)))
    for method, path in routes:
        mark = "OK  " if (method, path) in COVERED else "MISS"
        print("  [%s] %-6s %s" % (mark, method, path))
    if missing or stale:
        print("FAIL 未覆盖 %d / 多余 %d" % (len(missing), len(stale)))
        return 1
    print("PASS 覆盖 100%，无未登记路由")
    return 0


if __name__ == "__main__":
    sys.exit(main())
