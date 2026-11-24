-- #2442 · 虚构测试数据（PostgreSQL 16 / SQLite 3 通用）
-- 口径自检：S9 为软删除会所（其数据必须被所有汇总查询过滤）、E90 为软删除企业、
--           S1 有 1 条已离场关系、S3 在驻关系数(12) 大于工位数(8) 用于验证空置不为负。

INSERT INTO site (id, name, seats, status, deleted_at) VALUES
 ('S1', '光谷会所', 20, 'active', NULL),
 ('S2', '江汉会所', 12, 'active', NULL),
 ('S3', '汉阳会所',  8, 'active', NULL),
 ('S9', '青山会所', 10, 'active', '2026-08-31 10:00:00');

INSERT INTO enterprise (id, name, credit_code, org_id, deleted_at) VALUES
 ('E01', '虚构甲', '9142XXXX0001', 'ORG-1', NULL), ('E02', '虚构乙', '9142XXXX0002', 'ORG-1', NULL),
 ('E03', '虚构丙', '9142XXXX0003', 'ORG-1', NULL), ('E04', '虚构丁', '9142XXXX0004', 'ORG-1', NULL),
 ('E05', '虚构戊', '9142XXXX0005', 'ORG-1', NULL), ('E06', '虚构己', '9142XXXX0006', 'ORG-1', NULL),
 ('E07', '虚构庚', '9142XXXX0007', 'ORG-1', NULL), ('E08', '虚构辛', '9142XXXX0008', 'ORG-1', NULL),
 ('E09', '虚构壬', '9142XXXX0009', 'ORG-1', NULL), ('E10', '虚构癸', '9142XXXX0010', 'ORG-1', NULL),
 ('E11', '虚构子', '9142XXXX0011', 'ORG-1', NULL), ('E12', '虚构丑', '9142XXXX0012', 'ORG-1', NULL),
 ('E13', '虚构寅', '9142XXXX0013', 'ORG-1', NULL), ('E14', '虚构卯', '9142XXXX0014', 'ORG-1', NULL),
 ('E15', '虚构辰', '9142XXXX0015', 'ORG-1', NULL), ('E16', '虚构巳', '9142XXXX0016', 'ORG-1', NULL),
 ('E17', '虚构午', '9142XXXX0017', 'ORG-1', NULL), ('E18', '虚构未', '9142XXXX0018', 'ORG-1', NULL),
 ('E19', '虚构申', '9142XXXX0019', 'ORG-1', NULL), ('E20', '虚构酉', '9142XXXX0020', 'ORG-1', NULL),
 ('E21', '虚构戌', '9142XXXX0021', 'ORG-1', NULL), ('E22', '虚构亥', '9142XXXX0022', 'ORG-1', NULL),
 ('E23', '虚构宇', '9142XXXX0023', 'ORG-1', NULL), ('E90', '虚构注销企业', '9142XXXX0090', 'ORG-1', '2026-09-30 09:00:00');

-- S1：6 条在驻 + 1 条已离场
INSERT INTO enterprise_site (id, enterprise_id, site_id, status, started_at, ended_at) VALUES
 (1, 'E01', 'S1', 'in_house', '2026-01-05', NULL),
 (2, 'E02', 'S1', 'in_house', '2026-01-08', NULL),
 (3, 'E03', 'S1', 'in_house', '2026-02-11', NULL),
 (4, 'E04', 'S1', 'in_house', '2026-03-02', NULL),
 (5, 'E05', 'S1', 'in_house', '2026-04-19', NULL),
 (6, 'E06', 'S1', 'in_house', '2026-05-06', NULL),
 (7, 'E07', 'S1', 'left',     '2025-11-03', '2026-06-30');

-- S2：新增 E01 的第二条入驻关系（场景 S01：同一企业同时入驻两个会所）
INSERT INTO enterprise_site (id, enterprise_id, site_id, status, started_at, ended_at) VALUES
 (8,  'E08', 'S2', 'in_house', '2026-01-12', NULL),
 (9,  'E09', 'S2', 'in_house', '2026-02-20', NULL),
 (10, 'E10', 'S2', 'in_house', '2026-03-15', NULL),
 (11, 'E11', 'S2', 'in_house', '2026-07-01', NULL),
 (12, 'E90', 'S2', 'in_house', '2026-05-01', NULL),
 (27, 'E01', 'S2', 'in_house', '2026-08-01', NULL);

-- S3：12 条在驻（超出工位容量，验证空置不为负）
INSERT INTO enterprise_site (id, enterprise_id, site_id, status, started_at, ended_at) VALUES
 (13, 'E12', 'S3', 'in_house', '2026-01-02', NULL),
 (14, 'E13', 'S3', 'in_house', '2026-01-02', NULL),
 (15, 'E14', 'S3', 'in_house', '2026-01-02', NULL),
 (16, 'E15', 'S3', 'in_house', '2026-02-02', NULL),
 (17, 'E16', 'S3', 'in_house', '2026-02-02', NULL),
 (18, 'E17', 'S3', 'in_house', '2026-03-02', NULL),
 (19, 'E18', 'S3', 'in_house', '2026-03-02', NULL),
 (20, 'E19', 'S3', 'in_house', '2026-04-02', NULL),
 (21, 'E20', 'S3', 'in_house', '2026-04-02', NULL),
 (22, 'E21', 'S3', 'in_house', '2026-05-02', NULL),
 (23, 'E22', 'S3', 'in_house', '2026-05-02', NULL),
 (24, 'E23', 'S3', 'in_house', '2026-06-02', NULL);

-- S9（软删除会所）：必须被所有汇总 SQL 排除
INSERT INTO enterprise_site (id, enterprise_id, site_id, status, started_at, ended_at) VALUES
 (25, 'E01', 'S9', 'in_house', '2026-01-10', NULL),
 (26, 'E02', 'S9', 'in_house', '2026-01-10', NULL);

-- 活动：V01 公开（S1）、V15 私有（S9 会所私有活动的镜像，用于 S02 报名规则）
INSERT INTO event (id, site_id, month, kind, visibility) VALUES
 ('V01', 'S1', '2026-11', 'seminar', 'public'),
 ('V02', 'S1', '2026-11', 'salon',   'public'),
 ('V03', 'S1', '2026-11', 'salon',   'public'),
 ('V04', 'S1', '2026-11', 'visit',   'public'),
 ('V05', 'S1', '2026-11', 'seminar', 'public'),
 ('V06', 'S1', '2026-10', 'salon',   'public'),
 ('V07', 'S1', '2026-10', 'visit',   'public'),
 ('V08', 'S2', '2026-11', 'salon',   'public'),
 ('V09', 'S2', '2026-11', 'visit',   'public'),
 ('V10', 'S2', '2026-11', 'seminar', 'public'),
 ('V11', 'S2', '2026-10', 'salon',   'public'),
 ('V12', 'S3', '2026-11', 'salon',   'public'),
 ('V13', 'S3', '2026-11', 'visit',   'public'),
 ('V14', 'S9', '2026-11', 'salon',   'private'),
 ('V15', 'S9', '2026-11', 'salon',   'private'),
 ('V16', 'S9', '2026-11', 'visit',   'public'),
 ('V17', 'S9', '2026-11', 'visit',   'public');

-- S1 内部活动（会所私有，用于 S02 负向用例：B 会所会员报名 A 会所私有活动必须被拒）
INSERT INTO event (id, site_id, month, kind, visibility) VALUES
 ('V18', 'S1', '2026-11', 'salon', 'private');

INSERT INTO opportunity (id, site_id, stage, ent_id, owner_id, amount_cent) VALUES
 ('O01', 'S1', 'signed', 'E01', 'owner-s1-a1', 1200000),
 ('O02', 'S1', 'signed', 'E02', 'owner-s1-a1',  900000),
 ('O03', 'S1', 'signed', 'E03', 'owner-s1-a1',  640000),
 ('O04', 'S1', 'open',   'E04', 'owner-s1-a2',  300000),
 ('O05', 'S1', 'lost',   'E05', 'owner-s1-a2',  150000),
 ('O06', 'S2', 'signed', 'E08', 'owner-s2-b1',  800000),
 ('O07', 'S2', 'signed', 'E09', 'owner-s2-b1',  520000),
 ('O08', 'S2', 'open',   'E10', 'owner-s2-b1',  260000),
 ('O09', 'S3', 'signed', 'E12', 'owner-s3-c1',  410000),
 ('O10', 'S3', 'open',   'E13', 'owner-s3-c1',  100000),
 ('O11', 'S9', 'signed', 'E01', 'owner-s9-x1',  990000),
 ('O12', 'S9', 'open',   'E02', 'owner-s9-x1',   88000);

INSERT INTO sop_task (id, site_id, status) VALUES
 ('T01', 'S1', 'done'), ('T02', 'S1', 'done'), ('T03', 'S1', 'done'),
 ('T04', 'S1', 'done'), ('T05', 'S1', 'done'), ('T06', 'S1', 'done'),
 ('T07', 'S1', 'done'), ('T08', 'S1', 'done'), ('T09', 'S1', 'open'),
 ('T10', 'S1', 'open'),
 ('T11', 'S2', 'done'), ('T12', 'S2', 'done'), ('T13', 'S2', 'done'),
 ('T14', 'S2', 'open'), ('T15', 'S2', 'open'), ('T16', 'S2', 'skipped'),
 ('T17', 'S3', 'done'), ('T18', 'S3', 'done'), ('T19', 'S3', 'done'),
 ('T20', 'S3', 'done'),
 ('T21', 'S9', 'open'), ('T22', 'S9', 'open');

-- 联系人：ct-1 归属 S1（S03 场景中要真实迁到 S2），ct-2 属于将停业的 S2
INSERT INTO contact (id, ent_id, site_id, owner_id, deleted_at) VALUES
 ('ct-1', 'E01', 'S1', 'owner-s1-a1', NULL),
 ('ct-2', 'E08', 'S2', 'owner-s2-b1', NULL),
 ('ct-3', 'E02', 'S1', 'owner-s1-a1', NULL),
 ('ct-4', 'E09', 'S2', 'owner-s2-b1', NULL);

-- 知识库：机构共享 1 篇 + S1 私有 1 篇 + S2 私有 1 篇
INSERT INTO knowledge_article (id, title, scope, site_id) VALUES
 ('kb-org-1',   '机构统一服务标准', 'org',  NULL),
 ('kb-s1-1',    'S1 会所内部排班',   'site', 'S1'),
 ('kb-s2-1',    'S2 会所内部排班',   'site', 'S2');

-- 机构级字典：空间类型 office/hall；S1 额外扩展 coworking（会所可增不可覆写机构键）
INSERT INTO dict_entry (dict_key, code, label, scope, site_id) VALUES
 ('space_type', 'office',   '办公室',   'org',  ''),
 ('space_type', 'hall',     '活动厅',   'org',  ''),
 ('space_type', 'coworking','联合办公', 'site', 'S1');

-- 配置：S1 有会所专属保证金比例 20%，集团通用 30%
INSERT INTO group_config (cfg_key, cfg_value) VALUES
 ('deposit_ratio_bp', '3000'),
 ('min_lease_months', '6');

INSERT INTO site_config (site_id, cfg_key, cfg_value) VALUES
 ('S1', 'deposit_ratio_bp', '2000');
