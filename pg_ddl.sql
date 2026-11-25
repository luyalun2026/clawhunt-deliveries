-- calib.churn_label PostgreSQL 16 DDL（与 SQLite 演示版列定义一致）
CREATE SCHEMA IF NOT EXISTS calib;

CREATE TABLE IF NOT EXISTS calib.churn_label (
    company_pid    varchar(40) NOT NULL,
    snapshot_date  date        NOT NULL,
    label          smallint,
    label_reason   varchar(32),
    observed_until date        NOT NULL,
    CONSTRAINT pk_churn_label PRIMARY KEY (company_pid, snapshot_date),
    CONSTRAINT ck_label CHECK (label IN (0, 1) OR label IS NULL)
);

CREATE INDEX IF NOT EXISTS ix_churn_label_snapshot ON calib.churn_label (snapshot_date);
