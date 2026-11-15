-- CruxTrap schema. Idempotent: applied by the postgres image on first boot and by the
-- pipeline on every start.
--
--   attackers (1) ──< sessions (1) ──< session_actions
--   attackers (1) ──< login_attempts

CREATE TABLE IF NOT EXISTS attackers (
    src_ip               INET PRIMARY KEY,
    first_seen           TIMESTAMPTZ NOT NULL,
    last_seen            TIMESTAMPTZ NOT NULL,
    total_connections    INTEGER NOT NULL DEFAULT 0,
    total_login_attempts INTEGER NOT NULL DEFAULT 0,
    total_sessions       INTEGER NOT NULL DEFAULT 0,
    total_commands       INTEGER NOT NULL DEFAULT 0,
    last_username        TEXT,
    country_code         TEXT,
    country              TEXT,
    city                 TEXT,
    latitude             DOUBLE PRECISION,
    longitude            DOUBLE PRECISION,
    asn                  TEXT,
    org                  TEXT
);

CREATE TABLE IF NOT EXISTS login_attempts (
    id        BIGSERIAL PRIMARY KEY,
    ts        TIMESTAMPTZ NOT NULL,
    src_ip    INET NOT NULL REFERENCES attackers(src_ip) ON DELETE CASCADE,
    src_port  INTEGER,
    username  TEXT,
    password  TEXT,
    attempt   INTEGER,
    success   BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id    UUID PRIMARY KEY,
    src_ip        INET NOT NULL REFERENCES attackers(src_ip) ON DELETE CASCADE,
    src_port      INTEGER,
    username      TEXT,
    password      TEXT,
    started_at    TIMESTAMPTZ NOT NULL,
    ended_at      TIMESTAMPTZ,
    duration_s    DOUBLE PRECISION,
    pty           BOOLEAN,
    term          TEXT,
    exec_command  TEXT,
    command_count INTEGER NOT NULL DEFAULT 0,
    end_reason    TEXT,
    total_reward  DOUBLE PRECISION,
    epsilon       DOUBLE PRECISION,
    episode       INTEGER
);

CREATE TABLE IF NOT EXISTS session_actions (
    session_id     UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    seq            INTEGER NOT NULL,
    ts             TIMESTAMPTZ NOT NULL,
    command        TEXT NOT NULL,
    category       TEXT,
    phase          TEXT,
    state          TEXT,
    action         TEXT,
    epsilon        DOUBLE PRECISION,
    q_before       JSONB,
    latency_ms     INTEGER,
    output_bytes   INTEGER,
    decoys_planted BOOLEAN,
    -- filled in by the rl_update event that follows
    reward         DOUBLE PRECISION,
    continued      BOOLEAN,
    next_state     TEXT,
    q_after        JSONB,
    PRIMARY KEY (session_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_attackers_last_seen   ON attackers (last_seen DESC);
CREATE INDEX IF NOT EXISTS idx_login_attempts_ip     ON login_attempts (src_ip, ts DESC);
CREATE INDEX IF NOT EXISTS idx_login_attempts_ts     ON login_attempts (ts DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_ip           ON sessions (src_ip, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_started      ON sessions (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_actions_category      ON session_actions (category);
CREATE INDEX IF NOT EXISTS idx_actions_state_action  ON session_actions (state, action);
CREATE INDEX IF NOT EXISTS idx_actions_ts            ON session_actions (ts DESC);
