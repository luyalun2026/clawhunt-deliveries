# -*- coding: utf-8 -*-
"""招商线索可见性 / 越权用例的被测系统（内存实现，虚构数据）。

对外暴露一个极简 Api，返回 (status_code, body)；所有拒绝都必须留审计。
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Lead:
    id: str
    ent_name: str
    site_id: str
    owner_id: str | None          # None = 公海
    deleted: bool = False
    quote_cent: int = 0
    contract_id: str | None = None


@dataclass
class Actor:
    id: str
    role: str                     # consultant / supervisor / site_lead / unauthenticated
    site_id: str | None = None
    team: list[str] = field(default_factory=list)


NOT_FOUND = {"error": "not_found"}
FORBIDDEN = {"error": "forbidden", "code": "FORBIDDEN_NOT_OWNER"}


class Api:
    POOL = None

    def __init__(self, leads: list[Lead]):
        self.leads = {l.id: l for l in leads}
        self.audit: list[dict[str, Any]] = []

    # ------------------------------------------------------------ 可见性
    def _in_scope(self, actor: Actor, lead: Lead) -> bool:
        if lead.deleted:
            return False
        if actor.role == "consultant":
            return lead.owner_id == actor.id or lead.owner_id is None
        if actor.role == "supervisor":
            return lead.owner_id in actor.team or lead.owner_id is None
        if actor.role == "site_lead":
            return lead.site_id == actor.site_id
        return False

    def _deny(self, actor: Actor, resource: str, rid: str, path: str) -> None:
        self.audit.append({"actor_id": actor.id, "action": "access_denied",
                           "resource_type": resource, "resource_id": rid, "path": path,
                           "result": "denied"})

    @staticmethod
    def _normalize(path: str) -> str:
        p = path.strip().split("?")[0].rstrip("/")
        return p.lower().replace("%2e%2e", "")

    # ------------------------------------------------------------ 六类操作
    def list_leads(self, actor: Actor, path: str = "/api/leads") -> tuple[int, Any]:
        if actor.role == "unauthenticated":
            self._deny(actor, "lead", "*", path)
            return 401, {"error": "unauthorized"}
        rows = [self._row(l) for l in self.leads.values() if self._in_scope(actor, l)]
        return 200, {"items": rows, "total": len(rows)}

    def get_lead(self, actor: Actor, lead_id: str, path: str | None = None) -> tuple[int, Any]:
        path = path or f"/api/leads/{lead_id}"
        lead = self.leads.get(lead_id)
        if lead is None or not self._in_scope(actor, lead):
            self._deny(actor, "lead", lead_id, path)
            return 404, dict(NOT_FOUND)          # 不存在与不可见同响应，不泄露存在性
        return 200, self._row(lead)

    def get_quote(self, actor: Actor, lead_id: str) -> tuple[int, Any]:
        lead = self.leads.get(lead_id)
        if lead is None or not self._in_scope(actor, lead):
            self._deny(actor, "quote", lead_id, f"/api/leads/{lead_id}/quote")
            return 404, dict(NOT_FOUND)
        return 200, {"lead_id": lead_id, "quote_cent": lead.quote_cent}

    def get_contract(self, actor: Actor, lead_id: str) -> tuple[int, Any]:
        lead = self.leads.get(lead_id)
        if lead is None or not self._in_scope(actor, lead):
            self._deny(actor, "contract", lead_id, f"/api/leads/{lead_id}/contract")
            return 404, dict(NOT_FOUND)
        return 200, {"lead_id": lead_id, "contract_id": lead.contract_id}

    def change_owner(self, actor: Actor, lead_id: str, new_owner: str) -> tuple[int, Any]:
        lead = self.leads.get(lead_id)
        if lead is None or lead.deleted:
            self._deny(actor, "lead", lead_id, f"PATCH /api/leads/{lead_id}/owner")
            return 404, dict(NOT_FOUND)
        if actor.role == "consultant" and lead.owner_id != actor.id:
            self._deny(actor, "lead", lead_id, f"PATCH /api/leads/{lead_id}/owner")
            return 403, dict(FORBIDDEN)
        if actor.role == "consultant" and lead.owner_id is None:
            # 公海须走认领接口，不能直接改 owner
            self._deny(actor, "lead", lead_id, f"PATCH /api/leads/{lead_id}/owner")
            return 403, dict(FORBIDDEN)
        lead.owner_id = new_owner
        return 200, {"lead_id": lead_id, "owner_id": new_owner}

    def export_leads(self, actor: Actor, page: int = 1, size: int = 100) -> tuple[int, Any]:
        if actor.role == "unauthenticated":
            self._deny(actor, "export", "*", "/api/leads/export")
            return 401, {"error": "unauthorized"}
        rows = [self._row(l) for l in self.leads.values() if self._in_scope(actor, l)]
        start = (page - 1) * size
        return 200, {"rows": rows[start:start + size], "total": len(rows), "page": page}

    def search(self, actor: Actor, q: str) -> tuple[int, Any]:
        if actor.role == "unauthenticated":
            self._deny(actor, "search", q or "*", "/api/search")
            return 401, {"error": "unauthorized"}
        res = [self._row(l) for l in self.leads.values()
               if self._in_scope(actor, l) and (q or "").lower() in l.ent_name.lower()]
        return 200, {"items": res, "total": len(res), "q": q}

    # ------------------------------------------------------------ 辅助
    @staticmethod
    def _row(lead: Lead) -> dict[str, Any]:
        return {"id": lead.id, "ent_name": lead.ent_name, "site_id": lead.site_id,
                "owner_id": lead.owner_id}

    def audit_denied(self) -> list[dict[str, Any]]:
        return [a for a in self.audit if a["action"] == "access_denied"]

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy({k: vars(v) for k, v in self.leads.items()})


def seed() -> Api:
    """A、B 各 5 条线索 + 公海 3 条 + 1 条软删除（不计入 13）。"""
    leads = []
    for i in range(1, 6):
        leads.append(Lead(f"L-A{i}", f"虚构甲企业{i}", "site-a", "consultant-a",
                          quote_cent=100_000 * i, contract_id=f"CT-A{i}"))
    for i in range(1, 6):
        leads.append(Lead(f"L-B{i}", f"虚构乙企业{i}", "site-a", "consultant-b",
                          quote_cent=200_000 * i, contract_id=f"CT-B{i}"))
    for i in range(1, 4):
        leads.append(Lead(f"L-P{i}", f"虚构公海企业{i}", "site-a", None))
    leads.append(Lead("L-DEL", "虚构已删企业", "site-a", "consultant-b", deleted=True))
    leads.append(Lead("L-OTHER-SITE", "虚构他站企业", "site-b", "consultant-c"))
    return Api(leads)


A = Actor("consultant-a", "consultant")
B = Actor("consultant-b", "consultant")
SUP = Actor("supervisor-1", "supervisor", team=["consultant-a", "consultant-b"])
SITE_LEAD = Actor("site-lead-a", "site_lead", site_id="site-a")
ANON = Actor("anon", "unauthenticated")

ROLES = {"A": A, "B": B, "supervisor": SUP, "site_lead": SITE_LEAD, "anonymous": ANON}
