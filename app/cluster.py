# -*- coding: utf-8 -*-
"""密度聚类：互达距离 + 最小生成树 + 单链合并 + 「首个真簇合并」切点。

算法（与 HDBSCAN 共享同一套密度定义，切点规则做了可审计的简化）：
1. 互达距离 mutual reachability = max(core_k(i), core_k(j), d(i,j))，d = 1 − 余弦；
   core_k(i) 为第 k 近邻距离（k = min_cluster_size），这一步与 HDBSCAN 完全一致。
2. 用互达距离建 MST，边权升序即单链层次聚类的合并序列。
3. 按序合并，**记录第一次出现「两个规模都 ≥ min_cluster_size 的分量被合并」的边**，
   该边之前的状态即为切分结果。它的含义是：到这里两个已成形的簇开始粘连，
   再往前合并就会把不同失败模式并成一个（这正是 HDBSCAN 用稳定性选择要避免的情形）。
4. 切分后规模 ≥ min_cluster_size 的分量成簇，其余点标 -1（零散失败）。

若整份数据只有一个密度连通块（没有发生「真簇合并」），返回全部噪声并在 info 里标注
`degenerate=True`，不做强行切分。
"""
import math

from app.embed import cosine


def distance_matrix(vecs):
    n = len(vecs)
    d = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            dist = 1.0 - cosine(vecs[i], vecs[j])
            d[i][j] = d[j][i] = dist if dist > 0 else 0.0
    return d


def core_distances(d, k):
    n = len(d)
    k = max(1, min(k, n - 1))
    out = []
    for i in range(n):
        row = sorted(d[i][j] for j in range(n) if j != i)
        out.append(row[k - 1])
    return out


def mutual_reachability(d, core):
    n = len(d)
    m = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            v = max(core[i], core[j], d[i][j])
            m[i][j] = m[j][i] = v
    return m


def mst_edges(m):
    n = len(m)
    if n < 2:
        return []
    in_tree = [False] * n
    best = [math.inf] * n
    parent = [-1] * n
    best[0] = 0.0
    edges = []
    for _ in range(n):
        u, bu = -1, math.inf
        for i in range(n):
            if not in_tree[i] and best[i] < bu:
                u, bu = i, best[i]
        if u == -1:
            break
        in_tree[u] = True
        if parent[u] >= 0:
            edges.append((bu, parent[u], u))
        for v in range(n):
            if not in_tree[v] and m[u][v] < best[v]:
                best[v] = m[u][v]
                parent[v] = u
    edges.sort()
    return edges


class _DSU:
    def __init__(self, n):
        self.p = list(range(n))
        self.sz = [1] * n

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return ra, 0
        if self.sz[ra] < self.sz[rb]:
            ra, rb = rb, ra
        self.p[rb] = ra
        self.sz[ra] += self.sz[rb]
        return ra, self.sz[rb]


def candidate_merges(edges, n, min_cluster_size):
    """列出「两侧分量都 ≥ min_cluster_size」的合并边：[(edge_index, weight)]。"""
    dsu = _DSU(n)
    out = []
    for idx, (w, i, j) in enumerate(edges):
        ra, rb = dsu.find(i), dsu.find(j)
        if ra == rb:
            continue
        if dsu.sz[ra] >= min_cluster_size and dsu.sz[rb] >= min_cluster_size:
            out.append((idx, w))
        dsu.union(ra, rb)
    return out


def choose_cut(edges, n, min_cluster_size):
    """在候选合并里选「后续间隔最大」的那一处，返回 cut_index（合并前 cut 条边）。

    含义：两个已成形的簇走到这一步时，下一步合并的代价陡增（密度落差），
    说明此处就是自然分界；噪声点在小分量阶段就被并入，不会成为候选。
    """
    cands = candidate_merges(edges, n, min_cluster_size)
    if not cands:
        return len(edges), None
    scored = []
    for idx, w in cands:
        nxt = edges[idx + 1][0] if idx + 1 < len(edges) else w
        scored.append((nxt - w, idx, w))
    scored.sort(reverse=True)
    _, idx, w = scored[0]
    return idx + 1, w


def _labels_at(edges, n, cut, min_cluster_size):
    dsu = _DSU(n)
    for w, i, j in edges[:cut]:
        dsu.union(i, j)
    groups = {}
    for i in range(n):
        groups.setdefault(dsu.find(i), []).append(i)
    labels = [-1] * n
    cid = 0
    for root, members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        if len(members) >= min_cluster_size:
            for i in members:
                labels[i] = cid
            cid += 1
    return labels, groups


def hdbscan_lite(vecs, min_cluster_size=5, k_core=None):
    n = len(vecs)
    if n == 0:
        return [], {"clusters": 0, "noise": 0, "min_cluster_size": min_cluster_size}
    if n < min_cluster_size:
        return [-1] * n, {"clusters": 0, "noise": n, "reason": "样本不足一簇",
                          "min_cluster_size": min_cluster_size}

    d = distance_matrix(vecs)
    core = core_distances(d, k_core or min_cluster_size)
    m = mutual_reachability(d, core)
    edges = mst_edges(m)
    cut, cut_w = choose_cut(edges, n, min_cluster_size)
    labels, groups = _labels_at(edges, n, cut, min_cluster_size)

    if cut_w is None:
        # 没有发生「两个成形簇合并」：整份数据是一个密度连通块。
        # 若样本量已达到最小簇规模，按单一簇返回，但标记 degenerate=True（无间隙依据）。
        if n >= min_cluster_size:
            labels = [0] * n
            info = {"clusters": 1, "noise": 0, "degenerate": True,
                    "cluster_sizes": [n], "cut_weight": None, "mst_edges": len(edges),
                    "min_cluster_size": min_cluster_size,
                    "reason": "未出现两个成形簇的合并，按单一密度连通块返回"}
            return labels, info
        info = {"clusters": 0, "noise": n, "degenerate": True, "min_cluster_size": min_cluster_size,
                "mst_edges": len(edges), "reason": "未出现两个成形簇的合并"}
        return labels, info

    info = {
        "clusters": len(set(labels) - {-1}),
        "noise": sum(1 for x in labels if x == -1),
        "cluster_sizes": [len(v) for _, v in sorted(groups.items(), key=lambda kv: -len(kv[1]))
                          if len(v) >= min_cluster_size],
        "cut_weight": round(cut_w, 6),
        "degenerate": False,
        "mst_edges": len(edges),
        "min_cluster_size": min_cluster_size,
    }
    return labels, info


def adjusted_rand_index(a, b):
    from collections import Counter
    n = len(a)
    if n != len(b) or n == 0:
        raise ValueError("标签长度不一致")
    cont = Counter(zip(a, b))
    rows = Counter(a)
    cols = Counter(b)

    def c2(x):
        return x * (x - 1) / 2.0

    sum_ij = sum(c2(v) for v in cont.values())
    sum_i = sum(c2(v) for v in rows.values())
    sum_j = sum(c2(v) for v in cols.values())
    total = c2(n)
    expected = (sum_i * sum_j) / total if total else 0.0
    max_index = 0.5 * (sum_i + sum_j)
    denom = max_index - expected
    if denom == 0:
        return 1.0
    return (sum_ij - expected) / denom
