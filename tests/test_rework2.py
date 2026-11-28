# -*- coding: utf-8 -*-
"""返工整改专项：全过期优先级、缺口地址校验、路由输入防护。"""


def test_r1_all_stale_takes_precedence_over_low_score(chunk, gen, ask, gap):
    """可见切片全部过复审期时判 stale_docs（规则 5），即使它们同时全部低分。"""
    d = ask("会议室怎么预定",
            [chunk("C1", score=0.10, valid_until="2020-01-01"),
             chunk("C2", score=0.20, valid_until="2020-02-01")], gen)
    assert d.status == "refuse_kb"
    assert d.reason == "stale_docs"
    assert gap.last()["reason"] == "stale_docs"
    assert gen.calls == 0


def test_r2_mixed_stale_and_low_score_still_low_score(chunk, gen, ask):
    """混合状态（部分低分未过期 + 部分过期，且无达标切片）→ 非「全部过期」，仍判 low_score。"""
    d = ask("会议室怎么预定",
            [chunk("C1", score=0.10),
             chunk("C2", score=0.20, valid_until="2020-01-01")], gen)
    assert d.status == "refuse_kb"
    assert d.reason == "low_score"


def test_r3_high_score_but_all_stale(chunk, gen, ask):
    """高分但全部过期 → stale_docs（原有行为保持不变）。"""
    d = ask("会议室怎么预定", [chunk("C1", score=0.9, valid_until="2020-01-01")], gen)
    assert d.reason == "stale_docs"


def test_r4_gap_url_rejects_invalid_scheme_and_host():
    """KB_GAP_BASE_URL 必须为 http/https 且含主机名，防误配外传。"""
    from app.settings import Settings
    for bad in ("ftp://intranet/api", "not-a-url", "http:///no-host", "file:///etc/passwd"):
        try:
            Settings.from_env({"KB_GAP_BASE_URL": bad})
        except ValueError:
            pass
        else:
            raise AssertionError("应拒绝：%r" % bad)
    s = Settings.from_env({"KB_GAP_BASE_URL": "https://10.0.0.8:8443/kb/gaps"})
    assert s.gap_base_url.startswith("https://")
    d = Settings.from_env({})
    assert d.gap_base_url.startswith("http://stub.local")


def test_r5_router_input_hardened(router):
    """路由输入去控制字符、截断 2000 字（模式来自服务端配置，无 ReDoS 注入面）。"""
    assert router("\x00\x01\x02其他会员的营业额有多少") == "business"   # 控制字符不影响匹配
    assert router("a" * 2000 + "其他会员的营业额有多少") is None        # 关键词落在截断段之外
