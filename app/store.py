# -*- coding: utf-8 -*-
"""内存数据访问层与数据范围判定（S2-IAM 的接口桩）。

真实环境中本模块被 SQLAlchemy 仓储替换；数据范围规则保持：
顾问 = 仅本人名下对象；主管 = 本会所全部对象；财务 = 本 org 只读。
"""
import copy

from fixtures.data import build_db


def new_db():
    return copy.deepcopy(build_db())


def can_view(actor, obj):
    """对象对 actor 是否可见。跨 org / 非本人 / 非本会所一律不可见（上层统一 404）。"""
    if not obj:
        return False
    if obj.get("org_id") != actor.get("org_id"):
        return False
    role = actor.get("role")
    if obj.get("owner_id") == actor.get("id"):
        return True
    if role == "supervisor":
        return obj.get("site_id") == actor.get("site_id")
    if role == "finance":
        return True  # 本 org 只读，用于审批
    return False


def can_write(actor, obj):
    role = actor.get("role")
    if role == "finance":
        return False
    if obj.get("owner_id") == actor.get("id"):
        return True
    if role == "supervisor":
        return obj.get("site_id") == actor.get("site_id")
    return False


def visible_list(actor, items):
    return [i for i in items if can_view(actor, i)]
