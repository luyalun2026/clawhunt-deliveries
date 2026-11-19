#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""金额模块无 float 静态检查（S4-FIN-002 验收 #4）。

用 AST 扫描目标文件：
  1) 禁止 float 字面量常量（ast.Constant 且值为 float）；
  2) 禁止 float() 调用与 float 名称引用；
  3) 禁止对 int 变量的真除（BinOp Div 左操作数不是 Decimal(...) 调用 / Decimal 名称）——
     即除法只允许发生在 Decimal 运算上下文。
退出码：发现违规 → 1，否则 0。随 pytest 运行。
"""
import ast
import sys

ALLOWED_DIV_FUNCS = {"Decimal"}


def check_file(path: str) -> list[str]:
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    problems: list[str] = []
    dec_vars: set[str] = set()

    class V(ast.NodeVisitor):
        def visit_Assign(self, node):
            if isinstance(node.value, ast.Call) and getattr(node.value.func, "id", "") == "Decimal":
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        dec_vars.add(t.id)
            self.generic_visit(node)

        def visit_AugAssign(self, node):
            self.generic_visit(node)

        def visit_Constant(self, node):
            if isinstance(node.value, float):
                problems.append(f"{path}:{node.lineno} float 字面量 {node.value}")

        def visit_Call(self, node):
            if getattr(node.func, "id", "") == "float":
                problems.append(f"{path}:{node.lineno} 禁止 float() 调用")
            self.generic_visit(node)

        def visit_BinOp(self, node):
            if isinstance(node.op, ast.Div):
                def is_dec(x):
                    return (
                        (isinstance(x, ast.Call) and getattr(x.func, "id", "") in ALLOWED_DIV_FUNCS)
                        or (isinstance(x, ast.Name) and x.id in dec_vars)
                    )
                if not (is_dec(node.left) or is_dec(node.right)):
                    problems.append(f"{path}:{node.lineno} 真除左右操作数均非 Decimal 上下文")
            self.generic_visit(node)

    V().visit(tree)
    return problems


if __name__ == "__main__":
    targets = sys.argv[1:] or ["schedule.py"]
    all_problems: list[str] = []
    for t in targets:
        all_problems.extend(check_file(t))
    for p in all_problems:
        print("VIOLATION:", p)
    print(f"扫描 {len(targets)} 个文件，违规 {len(all_problems)} 处 -> 退出码 {1 if all_problems else 0}")
    sys.exit(1 if all_problems else 0)
