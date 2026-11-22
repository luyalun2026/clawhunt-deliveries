# -*- coding: utf-8 -*-
"""生成 SHA256SUMS.txt：递归遍历交付包，排除版本库与缓存。"""
import hashlib
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "repo.git", "__pycache__", ".pytest_cache"}
SKIP_FILES = {"SHA256SUMS.txt", "_files.txt", "1980.bundle", "2490.bundle"}

lines = []
for root, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for f in files:
        if f in SKIP_FILES or f.endswith(".pyc"):
            continue
        path = os.path.join(root, f)
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
        with open(path, "rb") as fh:
            lines.append("%s  %s" % (hashlib.sha256(fh.read()).hexdigest(), rel))

lines.sort(key=lambda x: x.split("  ")[1])
with open(os.path.join(ROOT, "SHA256SUMS.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
print(len(lines), "files")
for line in lines:
    print("  " + line.split("  ")[1])
