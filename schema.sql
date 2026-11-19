-- PostgreSQL 16 DDL（生产环境）。SQLite 同构实现见 eval_runner/store.py。
-- 统一字段：id(UUID) / org_id / site_id / created_at / created_by / updated_at / deleted_at

CREATE TABLE IF NOT EXISTS eval_run (
    id              UUID PRIMARY KEY,
    org_id          UUID NOT NULL,
    site_id         UUID NOT NULL,
    suite_key       TEXT NOT NULL,
    target          TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'running',
    options_json    JSONB NOT NULL DEFAULT '{}'::jsonb,
    total           INTEGER NOT NULL DEFAULT 0,
    pass_rate       NUMERIC(6,4),
    exit_code       INTEGER,
    duration_ms     INTEGER,
    created_by      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS eval_result (
    id              UUID PRIMARY KEY,
    org_id          UUID NOT NULL,
    site_id         UUID NOT NULL,
    run_id          UUID NOT NULL REFERENCES eval_run(id) ON DELETE CASCADE,
    case_id         TEXT NOT NULL,
    status          TEXT NOT NULL,          -- passed | failed | error
    latency_ms      INTEGER NOT NULL,
    attempts        INTEGER NOT NULL,
    tokens_in       INTEGER NOT NULL DEFAULT 0,
    tokens_out      INTEGER NOT NULL DEFAULT 0,
    error           TEXT,
    output_json     JSONB,
    created_by      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ,
    CONSTRAINT uq_eval_result_run_case UNIQUE (run_id, case_id)
);

CREATE INDEX IF NOT EXISTS idx_eval_result_run ON eval_result (run_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_eval_result_status ON eval_result (status);
