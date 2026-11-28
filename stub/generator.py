# -*- coding: utf-8 -*-
"""生成模型桩：强制引用模式。用于断言"拒答路径零调用"以及引用校验的降级路径。

生产由 RAG_LLM_BASE_URL 注入真实模型；桩只做两件事：
1. 用给定切片拼一个带引用的答案（引用片段严格取自切片原文，保证能过校验）；
2. 记录调用次数，供 mock 断言。
"""


class Generator:
    def __init__(self, mode="normal", paraphrase=False, fake_chunk_id=None, drop_snippet=False):
        self.mode = mode                 # normal | bad_citation | partial_bad | broken_json
        self.paraphrase = paraphrase     # True 时引用片段被改写 → 校验应失败
        self.fake_chunk_id = fake_chunk_id
        self.drop_snippet = drop_snippet
        self.calls = 0
        self.last_prompt_chunks = []

    def __call__(self, *, question, chunks):
        self.calls += 1
        self.last_prompt_chunks = [c["chunk_id"] for c in chunks]
        lead = chunks[0]
        if self.fake_chunk_id or self.mode in ("bad_citation", "partial_bad"):
            cites = [{"chunk_id": self.fake_chunk_id or "C-NOT-EXIST",
                      "snippet": lead.get("text", "")[:20]}]
            if self.mode == "partial_bad":
                cites.insert(0, {"chunk_id": lead["chunk_id"], "snippet": lead.get("text", "")[:20]})
            return {"answer": "根据知识库整理：%s" % lead.get("text", "")[:40], "citations": cites}
        snippet = "" if self.drop_snippet else lead.get("text", "")[:max(4, min(30, len(lead.get("text", ""))))]
        if self.paraphrase:
            snippet = "改写过的片段" + snippet[-4:]
        return {"answer": "根据知识库整理：%s" % lead.get("text", "")[:40],
                "citations": [{"chunk_id": lead["chunk_id"], "snippet": snippet}]}

    def reset(self):
        self.calls = 0
        self.last_prompt_chunks = []
