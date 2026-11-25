#!/usr/bin/env python3
"""生成 44 张虚构界面/物料 SVG 演示语料（工作台 12、小程序 12、官网 6、物料 10、页面 4 补充 = 44）。

确定性：固定随机种子，重跑产物逐字节一致（写入 manifest.json 便于核对）。
SVG 中故意注入与规范有偏差的属性，供审计管线检出。
"""
import json, os, random

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "corpus", "shots")

PALETTE_OK = ["#1F5FBF", "#0F7A4A", "#B45309", "#1F2937", "#FFFFFF", "#EEF2F7", "#F7F8FA"]
PALETTE_BAD = ["#E74C3C", "#9B59B6", "#F1C40F", "#2C3E50", "#16A085"]
FONTS_OK = "'TCloud Sans', 'Microsoft YaHei', sans-serif"
FONTS_BAD = "Comic Sans MS, cursive"
SIZES_OK = [12, 14, 16, 20, 24, 32]
COPY_OK = ["会员空间", "产业资源对接", "本周活动安排", "提交申请", "查看详情", "联系顾问", "预约参观"]
COPY_BAD = ["超值爆款限时秒杀", "全网最低价霸王餐"]

random.seed(20261125)

PAGES = (
    [("console", f"工作台高频页面 p{i:02d}") for i in range(1, 13)]
    + [("miniapp", f"小程序页面 m{i:02d}") for i in range(1, 13)]
    + [("website", f"官网页面 w{i:02d}") for i in range(1, 7)]
    + [("poster", f"活动海报 ph{i:02d}") for i in range(1, 6)]
    + [("material", f"公众号头图 mt{i:02d}") for i in range(1, 6)]
    + [("console", f"驾驶舱页面 p13"), ("miniapp", f"小程序页面 m13"),
       ("website", f"官网页面 w07"), ("poster", f"活动海报 ph06")]
)
assert len(PAGES) == 44


def gen_svg(kind: str, label: str, idx: int) -> str:
    r = random.Random(1000 + idx)
    W, H = (900, 560) if kind in ("console", "website") else (375, 600) if kind == "miniapp" else (600, 800)
    bg = r.choice(["#FFFFFF", "#F7F8FA"])
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
             f'<rect id="bg" x="0" y="0" width="{W}" height="{H}" fill="{bg}"/>']

    # 顶部导航 + logo（每 6 张出现一次 logo 变形/过小）
    parts.append(f'<rect id="nav" x="0" y="0" width="{W}" height="56" fill="#1F5FBF"/>')
    if idx % 6 == 3:
        lw = 44  # 过小
    elif idx % 13 == 7:
        lw = 132  # 比例变形
    else:
        lw = 96
    parts.append(f'<rect id="logo" x="16" y="12" width="{lw}" height="32" fill="#FFFFFF"/>')
    parts.append(f'<rect id="logo_mark" x="{16+4}" y="16" width="{max(8, lw-8)}" height="24" fill="#1F5FBF"/>')

    # 正文文本行
    n_lines = r.randint(4, 6)
    y = 100
    for i in range(n_lines):
        font = FONTS_OK if (idx % 5 != 2 or i != 1) else FONTS_BAD
        size = r.choice(SIZES_OK)
        if idx % 7 == 1 and i == 0:
            size = 15  # 层级外字号
        color = "#1F2937"
        if idx % 4 == 0 and i == 2:
            color = r.choice(["#C8CDD4", "#D6DBE1"])  # 低对比
        if idx % 9 == 5 and i == 3:
            color = r.choice(PALETTE_BAD)  # 越界色
        txt = COPY_BAD if (idx % 11 == 6 and i == 1) else r.choice(COPY_OK)
        x = 32 if (idx % 8 != 4 or i != 2) else 30  # 30 不在 8px 栅格
        large = 'font-weight="700"' if size >= 24 else ""
        parts.append(f'<text id="t{i}" x="{x}" y="{y}" font-family="{font}" font-size="{size}" fill="{color}" {large}>{txt}</text>')
        y += int(size) + 22

    # 按钮 / 图标
    btn_fill = "#1F5FBF" if idx % 10 != 3 else r.choice(PALETTE_BAD)
    parts.append(f'<rect id="btn" x="32" y="{H-90}" width="140" height="40" rx="4" fill="{btn_fill}"/>')
    parts.append(f'<text x="44" y="{H-64}" font-family="{FONTS_OK}" font-size="14" fill="#FFFFFF">查看详情</text>')
    stroke = 2 if idx % 12 != 5 else 5  # 图标笔画越界
    parts.append(f'<rect id="icon1" x="{W-80}" y="72" width="28" height="28" fill="none" stroke="#1F2937" stroke-width="{stroke}"/>')

    # 插图占位（部分用越界色）
    ill_fill = "#EEF2F7" if idx % 6 != 1 else r.choice(PALETTE_BAD)
    parts.append(f'<rect id="illustration" x="{W-260}" y="{H//2-70}" width="200" height="140" rx="6" fill="{ill_fill}"/>')
    parts.append("</svg>")
    return "\n".join(parts)


def main():
    os.makedirs(OUT, exist_ok=True)
    manifest = []
    for idx, (kind, label) in enumerate(PAGES, 1):
        fname = f"{idx:03d}_{kind}.svg"
        svg = gen_svg(kind, label, idx)
        open(os.path.join(OUT, fname), "w", encoding="utf-8", newline="\n").write(svg)
        manifest.append({"file": f"shots/{fname}", "kind": kind, "label": label})
    json.dump(manifest, open(os.path.join(ROOT, "corpus", "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"generated {len(manifest)} SVG -> corpus/shots/")


if __name__ == "__main__":
    main()
