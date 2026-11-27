import hashlib
import os

files = []
for r, d, fs in os.walk("."):
    if "__pycache__" in r or ".pytest_cache" in r:
        continue
    for f in fs:
        p = os.path.join(r, f).replace(os.sep, "/")
        if p.endswith(".pyc") or p.endswith("SHA256SUMS"):
            continue
        files.append(p)
files.sort()
with open("SHA256SUMS", "w", encoding="utf-8") as o:
    for p in files:
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        o.write(f"{h}  {p[2:]}\n")
print(len(files), "files hashed")
