# -*- coding: utf-8 -*-
"""CRM 线索库接口桩（依赖 S2-CRM，本单先用桩）；返回拒绝原因代号。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .normalize import normalize_name


@dataclass
class Member:
    uscc: str | None
    name_norm: str
    churned_at: datetime | None = None


@dataclass
class Follow:
    uscc: str | None
    name_norm: str
    followed_at: datetime | None = None


class CrmStub:
    def __init__(self) -> None:
        self.members: list[Member] = []
        self.follows: list[Follow] = []

    # ------------------------------------------------------------ 夹具写入
    def add_member(self, uscc: str | None = None, name: str | None = None,
                   churned_at: datetime | None = None) -> "CrmStub":
        self.members.append(Member(uscc, normalize_name(name or ""), churned_at))
        return self

    def add_follow(self, uscc: str | None = None, name: str | None = None,
                   followed_at: datetime | None = None) -> "CrmStub":
        self.follows.append(Follow(uscc, normalize_name(name or ""), followed_at))
        return self

    # ------------------------------------------------------------ 查询
    def check(self, uscc: str | None, name: str, now: datetime,
              churn_window_days: int = 365, follow_window_days: int = 60) -> str | None:
        """返回 EXISTING_MEMBER / CHURNED_WITHIN_12M / FOLLOWED_WITHIN_60D / None。"""
        name_norm = normalize_name(name)
        for member in self.members:
            if not self._match(member.uscc, member.name_norm, uscc, name_norm):
                continue
            if member.churned_at is None:
                return "EXISTING_MEMBER"
            if now - member.churned_at <= timedelta(days=churn_window_days):
                return "CHURNED_WITHIN_12M"
        for follow in self.follows:
            if not self._match(follow.uscc, follow.name_norm, uscc, name_norm):
                continue
            if follow.followed_at is not None and now - follow.followed_at <= timedelta(days=follow_window_days):
                return "FOLLOWED_WITHIN_60D"
        return None

    @staticmethod
    def _match(crm_uscc: str | None, crm_name: str, uscc: str | None, name: str) -> bool:
        if uscc and crm_uscc:
            return uscc.upper() == crm_uscc.upper()
        return bool(name) and crm_name == name
