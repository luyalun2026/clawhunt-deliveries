-- #2442 · 共享数据与会所级数据边界验证 —— 测试库 DDL
-- 目标引擎：PostgreSQL 16（本单统一技术约定）。
-- 为便于 5+5 汇总 SQL 离线复跑，核心 6 张表同时兼容 SQLite 3；
-- 12 个场景所需的接口桩（PL/pgSQL 函数）单独放在 sql/00_api_pg.sql，仅 PostgreSQL 16 执行。
-- 全部字段为虚构，不含任何客户真实名称/数据。

DROP TABLE IF EXISTS scenario_result;
DROP TABLE IF EXISTS referral;
DROP TABLE IF EXISTS event_registration;
DROP TABLE IF EXISTS contact_owner_history;
DROP TABLE IF EXISTS contact;
DROP TABLE IF EXISTS knowledge_article;
DROP TABLE IF EXISTS dict_entry;
DROP TABLE IF EXISTS site_config;
DROP TABLE IF EXISTS group_config;
DROP TABLE IF EXISTS sop_task;
DROP TABLE IF EXISTS opportunity;
DROP TABLE IF EXISTS event;
DROP TABLE IF EXISTS enterprise_site;
DROP TABLE IF EXISTS enterprise;
DROP TABLE IF EXISTS site;

CREATE TABLE site (
    id          TEXT PRIMARY KEY,              -- 会所编号
    name        TEXT NOT NULL,
    seats       INTEGER NOT NULL,              -- 工位容量
    status      TEXT NOT NULL,                 -- active / closed
    deleted_at  TEXT NULL                      -- 软删除时间（NULL=有效）
);

CREATE TABLE enterprise (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    credit_code  TEXT NOT NULL,                -- 统一社会信用代码（机构内唯一）
    org_id       TEXT NOT NULL,                -- 所属机构
    deleted_at   TEXT NULL
);

CREATE TABLE enterprise_site (
    id              INTEGER PRIMARY KEY,
    enterprise_id   TEXT NOT NULL REFERENCES enterprise(id),
    site_id         TEXT NOT NULL REFERENCES site(id),
    status          TEXT NOT NULL,             -- in_house / left
    started_at      TEXT NOT NULL,
    ended_at        TEXT NULL                  -- 离场时间（NULL=仍在驻）
);

CREATE TABLE event (
    id          TEXT PRIMARY KEY,
    site_id     TEXT NOT NULL REFERENCES site(id),
    month       TEXT NOT NULL,                 -- 'YYYY-MM'
    kind        TEXT NOT NULL,
    visibility  TEXT NOT NULL DEFAULT 'public' -- public / private
);

CREATE TABLE opportunity (
    id           TEXT PRIMARY KEY,
    site_id      TEXT NOT NULL REFERENCES site(id),   -- 归属会所（转介后改为目标会所）
    stage        TEXT NOT NULL,                       -- open / signed / lost
    ent_id       TEXT NULL REFERENCES enterprise(id),
    owner_id     TEXT NULL,
    amount_cent  BIGINT NULL                          -- 金额（分）；跨会所视角必须脱敏
);

CREATE TABLE sop_task (
    id       TEXT PRIMARY KEY,
    site_id  TEXT NOT NULL REFERENCES site(id),
    status   TEXT NOT NULL                     -- done / open / skipped
);

CREATE TABLE contact (
    id          TEXT PRIMARY KEY,
    ent_id      TEXT NOT NULL REFERENCES enterprise(id),
    site_id     TEXT NOT NULL REFERENCES site(id),   -- 联系人归属会所
    owner_id    TEXT NOT NULL,
    deleted_at  TEXT NULL
);

CREATE TABLE contact_owner_history (
    id          INTEGER PRIMARY KEY,
    contact_id  TEXT NOT NULL REFERENCES contact(id),
    from_owner  TEXT NOT NULL,
    to_owner    TEXT NOT NULL,
    from_site   TEXT NOT NULL,
    to_site     TEXT NOT NULL,
    changed_at  TEXT NOT NULL
);

CREATE TABLE knowledge_article (
    id       TEXT PRIMARY KEY,
    title    TEXT NOT NULL,
    scope    TEXT NOT NULL,                    -- org / site
    site_id  TEXT NULL                         -- scope=site 时的归属会所
);

CREATE TABLE dict_entry (
    dict_key  TEXT NOT NULL,                   -- 字典名，如 space_type
    code      TEXT NOT NULL,
    label     TEXT NOT NULL,
    scope     TEXT NOT NULL,                   -- org / site
    site_id   TEXT NOT NULL DEFAULT '',        -- scope=site 时归属会所；机构级用空串（PK 不允许 NULL）
    PRIMARY KEY (dict_key, code, scope, site_id)
);

CREATE TABLE site_config (
    site_id   TEXT NOT NULL,
    cfg_key   TEXT NOT NULL,
    cfg_value TEXT NOT NULL,
    PRIMARY KEY (site_id, cfg_key)
);

CREATE TABLE group_config (
    cfg_key   TEXT NOT NULL PRIMARY KEY,
    cfg_value TEXT NOT NULL
);

CREATE TABLE event_registration (
    id          INTEGER PRIMARY KEY,
    event_id    TEXT NOT NULL REFERENCES event(id),
    ent_id      TEXT NOT NULL REFERENCES enterprise(id),
    member_site TEXT NOT NULL,                 -- 报名方所属会所
    host_site   TEXT NOT NULL,                 -- 活动主办会所
    created_at  TEXT NOT NULL
);

CREATE TABLE referral (
    id              INTEGER PRIMARY KEY,
    opportunity_id  TEXT NOT NULL REFERENCES opportunity(id),
    from_site       TEXT NOT NULL,
    to_site         TEXT NOT NULL,
    from_owner      TEXT NOT NULL,
    to_owner        TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

-- 场景执行结果落库表：每个场景脚本最后写入一行，对拍脚本从库里读回，不在 Python 侧拼数字
CREATE TABLE scenario_result (
    scenario  TEXT PRIMARY KEY,
    expected  TEXT NOT NULL,
    actual    TEXT NOT NULL,
    ok        BOOLEAN NOT NULL
);

CREATE INDEX idx_es_site ON enterprise_site(site_id, status, ended_at);
CREATE INDEX idx_ev_site_month ON event(site_id, month);
CREATE INDEX idx_op_site_stage ON opportunity(site_id, stage);
CREATE INDEX idx_sop_site_status ON sop_task(site_id, status);
CREATE INDEX idx_ct_site ON contact(site_id, owner_id, deleted_at);
