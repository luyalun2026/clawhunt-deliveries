# -*- coding: utf-8 -*-
"""确定性向量器：字符 3-gram 哈希 + TF 加权 + L2 归一化（纯标准库，无 numpy 依赖）。

生产用本地嵌入模型（EVAL_EMBED_BASE_URL）；离线路径用于 CI 与无模型环境复现，
两者的契约都是 embed(texts) -> list[list[float]]，维度固定 DIM。
"""
import hashlib
import math
import re

DIM = 512
_NORM = re.compile(r"\s+")


def _grams(text):
    t = _NORM.sub(" ", str(text or "")).strip()
    if len(t) < 3:
        return [t] if t else []
    return [t[i:i + 3] for i in range(len(t) - 2)]


def _bucket(gram):
    h = hashlib.md5(gram.encode("utf-8")).hexdigest()
    return int(h[:8], 16) % DIM


def embed(texts, dim=DIM):
    out = []
    for text in texts:
        vec = [0.0] * dim
        grams = _grams(text)
        if not grams:
            out.append(vec)
            continue
        for g in grams:
            vec[_bucket(g)] += 1.0
        # sublinear TF，压低高频 gram
        vec = [(1.0 + math.log(v)) if v > 0 else 0.0 for v in vec]
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        out.append([v / norm for v in vec])
    return out


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b))
