-- ============================================================
-- InDataLab v2 - Schema PostgreSQL para Neon
-- Gerado a partir dos modelos SQLAlchemy em app/models/
--
-- ATENCAO:
-- 1) Execute preferencialmente em um banco Neon vazio.
-- 2) CREATE TABLE IF NOT EXISTS nao atualiza tabelas antigas.
--    Se ja houver tabelas, compare o schema antes de executar.
-- 3) Tipos DateTime do projeto sao TIMESTAMP WITHOUT TIME ZONE.
-- 4) O ORM usa JSON (nao JSONB), portanto este script preserva JSON.
-- ============================================================

BEGIN;

SET search_path TO public;

-- ------------------------------------------------------------
-- ENUMS
-- KernelType e persistido por nome do membro Python:
-- PYTHON3, R, SQL.
-- ------------------------------------------------------------
DO $$
BEGIN
    CREATE TYPE kerneltype AS ENUM ('PYTHON3', 'R', 'SQL');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

DO $$
BEGIN
    CREATE TYPE cell_types AS ENUM ('python', 'sql', 'markdown', 'ai');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

DO $$
BEGIN
    CREATE TYPE cell_status AS ENUM ('idle', 'running', 'success', 'error');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

DO $$
BEGIN
    CREATE TYPE output_types AS ENUM (
        'text',
        'html',
        'json',
        'table',
        'chart',
        'image',
        'markdown',
        'error',
        'html_path',
        'image_path'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

-- ------------------------------------------------------------
-- 1. USERS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(120) NOT NULL,
    email               VARCHAR(120) NOT NULL,
    password_hash       TEXT NOT NULL,
    is_active           BOOLEAN DEFAULT TRUE,
    is_superuser        BOOLEAN DEFAULT FALSE,
    reset_token         VARCHAR(100),
    reset_token_expiry  TIMESTAMP WITHOUT TIME ZONE,
    avatar_url          TEXT,
    created_at          TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_users_reset_token UNIQUE (reset_token)
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email
    ON users (email);
CREATE INDEX IF NOT EXISTS ix_users_is_active
    ON users (is_active);

-- ------------------------------------------------------------
-- 2. NOTEBOOKS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notebooks (
    id                      SERIAL PRIMARY KEY,
    user_id                 INTEGER NOT NULL REFERENCES users(id),
    title                   VARCHAR(255) NOT NULL,
    description             TEXT,
    is_public               BOOLEAN DEFAULT FALSE,
    is_archived             BOOLEAN DEFAULT FALSE,
    kernel_type             kerneltype NOT NULL DEFAULT 'PYTHON3',
    default_sql_connection  VARCHAR(500),
    e2b_sandbox_id           VARCHAR(120),
    e2b_sandbox_expires_at   TIMESTAMP WITHOUT TIME ZONE,
    created_at              TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_notebooks_user_id
    ON notebooks (user_id);
CREATE INDEX IF NOT EXISTS ix_notebooks_is_public
    ON notebooks (is_public);
CREATE UNIQUE INDEX IF NOT EXISTS uq_notebooks_e2b_sandbox_id
    ON notebooks (e2b_sandbox_id);

-- ------------------------------------------------------------
-- 3. DATASETS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS datasets (
    id                  SERIAL PRIMARY KEY,
    notebook_id         INTEGER NOT NULL REFERENCES notebooks(id),
    filename            VARCHAR(255) NOT NULL,
    file_type           VARCHAR(20) NOT NULL,
    relative_path       VARCHAR(500) NOT NULL,
    file_size           BIGINT,
    rows                INTEGER,
    columns             INTEGER,
    column_names        JSON,
    description         TEXT,
    is_public           BOOLEAN DEFAULT FALSE,
    is_sql_database     BOOLEAN DEFAULT FALSE,
    file_hash           VARCHAR(64),
    uploaded_by_user_id INTEGER REFERENCES users(id),
    extra_metadata      JSON,
    created_at          TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_datasets_relative_path UNIQUE (relative_path)
);

CREATE INDEX IF NOT EXISTS ix_datasets_notebook_id
    ON datasets (notebook_id);

-- ------------------------------------------------------------
-- 4. CELLS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cells (
    id                  SERIAL PRIMARY KEY,
    uuid                VARCHAR(36) NOT NULL,
    notebook_id         INTEGER NOT NULL REFERENCES notebooks(id),
    dataset_id          INTEGER REFERENCES datasets(id),
    cell_type           cell_types NOT NULL DEFAULT 'python',
    language            VARCHAR(50) DEFAULT 'python',
    title               VARCHAR(255),
    content             TEXT NOT NULL DEFAULT '',
    content_hash        VARCHAR(64),
    tags                JSON DEFAULT '[]'::json,
    metadata_json       JSON,
    ai_context          TEXT,
    is_ai_generated     BOOLEAN DEFAULT FALSE,
    status              cell_status NOT NULL DEFAULT 'idle',
    execution_count     INTEGER DEFAULT 0,
    execution_time      DOUBLE PRECISION,
    last_executed_at    TIMESTAMP WITHOUT TIME ZONE,
    sql_connection      VARCHAR(255),
    output_type         output_types DEFAULT 'text',
    output              TEXT,
    output_json         JSON,
    error_output        TEXT,
    rows_returned       INTEGER,
    query_plan          TEXT,
    memory_usage        DOUBLE PRECISION,
    cpu_usage           DOUBLE PRECISION,
    position            INTEGER NOT NULL,
    version             INTEGER DEFAULT 1,
    is_hidden           BOOLEAN DEFAULT FALSE,
    is_collapsed        BOOLEAN DEFAULT FALSE,
    is_readonly         BOOLEAN DEFAULT FALSE,
    is_pinned           BOOLEAN DEFAULT FALSE,
    is_deleted          BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_cells_uuid
    ON cells (uuid);
CREATE INDEX IF NOT EXISTS ix_cells_notebook_id
    ON cells (notebook_id);
CREATE INDEX IF NOT EXISTS ix_cells_dataset_id
    ON cells (dataset_id);
CREATE INDEX IF NOT EXISTS ix_cells_cell_type
    ON cells (cell_type);
CREATE INDEX IF NOT EXISTS ix_cells_content_hash
    ON cells (content_hash);
CREATE INDEX IF NOT EXISTS ix_cells_status
    ON cells (status);
CREATE INDEX IF NOT EXISTS ix_cells_position
    ON cells (position);
CREATE INDEX IF NOT EXISTS ix_cells_is_deleted
    ON cells (is_deleted);
CREATE INDEX IF NOT EXISTS ix_cells_notebook_position
    ON cells (notebook_id, position);

-- ------------------------------------------------------------
-- 5. EXECUTIONS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS executions (
    id              SERIAL PRIMARY KEY,
    cell_id         INTEGER NOT NULL REFERENCES cells(id),
    status          VARCHAR(20) DEFAULT 'pending',
    execution_time  DOUBLE PRECISION,
    logs            TEXT,
    error_message   TEXT,
    memory_used     DOUBLE PRECISION,
    executed_at     TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at      TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_executions_cell_id
    ON executions (cell_id);
CREATE INDEX IF NOT EXISTS ix_executions_status
    ON executions (status);
CREATE INDEX IF NOT EXISTS ix_executions_executed_at
    ON executions (executed_at);
CREATE INDEX IF NOT EXISTS ix_executions_cell_status
    ON executions (cell_id, status);

-- ------------------------------------------------------------
-- 6. CELL CACHE
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cell_cache (
    id                  SERIAL PRIMARY KEY,
    content_hash        VARCHAR(64) NOT NULL,
    output              TEXT,
    output_json         JSON,
    execution_time      DOUBLE PRECISION,
    rows_returned       INTEGER,
    created_at          TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at    TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at          TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP + INTERVAL '24 hours')
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_cell_cache_content_hash
    ON cell_cache (content_hash);
CREATE INDEX IF NOT EXISTS ix_cell_cache_expires_at
    ON cell_cache (expires_at);

-- ------------------------------------------------------------
-- 7. CELL DEPENDENCIES
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cell_dependencies (
    id                  SERIAL PRIMARY KEY,
    cell_id             INTEGER NOT NULL REFERENCES cells(id) ON DELETE CASCADE,
    depends_on_cell_id  INTEGER NOT NULL REFERENCES cells(id) ON DELETE CASCADE,
    dependency_type     VARCHAR(20) NOT NULL DEFAULT 'data',
    CONSTRAINT uq_cell_dependency UNIQUE (cell_id, depends_on_cell_id)
);

CREATE INDEX IF NOT EXISTS ix_cell_dependencies_cell_id
    ON cell_dependencies (cell_id);
CREATE INDEX IF NOT EXISTS ix_cell_dependencies_depends_on_cell_id
    ON cell_dependencies (depends_on_cell_id);
CREATE INDEX IF NOT EXISTS ix_cell_dependencies_pair
    ON cell_dependencies (cell_id, depends_on_cell_id);

-- ------------------------------------------------------------
-- 8. CELL VERSIONS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cell_versions (
    id              SERIAL PRIMARY KEY,
    cell_id         INTEGER NOT NULL REFERENCES cells(id) ON DELETE CASCADE,
    version         INTEGER NOT NULL,
    content         TEXT NOT NULL,
    content_hash    VARCHAR(64) NOT NULL,
    created_by      INTEGER,
    created_at      TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_cell_versions_cell_id
    ON cell_versions (cell_id);
CREATE INDEX IF NOT EXISTS ix_cell_versions_content_hash
    ON cell_versions (content_hash);

-- ------------------------------------------------------------
-- 9. AI CONVERSATION SESSIONS
-- Criada antes de ai_conversations por causa da FK session_id.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ai_conversation_sessions (
    id              SERIAL PRIMARY KEY,
    session_uuid    VARCHAR(36) NOT NULL,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    title           VARCHAR(255),
    summary         TEXT,
    primary_model   VARCHAR(100),
    total_tokens    INTEGER DEFAULT 0,
    created_at      TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_ai_conversation_sessions_session_uuid
    ON ai_conversation_sessions (session_uuid);
CREATE INDEX IF NOT EXISTS ix_ai_conversation_sessions_user_id
    ON ai_conversation_sessions (user_id);

-- ------------------------------------------------------------
-- 10. AI CONVERSATIONS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ai_conversations (
    id                      SERIAL PRIMARY KEY,
    user_id                 INTEGER NOT NULL REFERENCES users(id),
    notebook_id             INTEGER REFERENCES notebooks(id) ON DELETE SET NULL,
    cell_id                 INTEGER REFERENCES cells(id) ON DELETE SET NULL,
    session_id              INTEGER REFERENCES ai_conversation_sessions(id) ON DELETE SET NULL,
    conversation_session_id VARCHAR(100),
    role                    VARCHAR(20) NOT NULL DEFAULT 'user',
    content                 TEXT NOT NULL,
    model                   VARCHAR(100) DEFAULT 'llama-3.3-70b-versatile',
    temperature             DOUBLE PRECISION DEFAULT 0.7,
    tokens_used             INTEGER,
    input_tokens            INTEGER,
    output_tokens           INTEGER,
    processing_time         DOUBLE PRECISION,
    groq_request_id         VARCHAR(100),
    extra_metadata          TEXT,
    created_at              TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_ai_conversations_user_id
    ON ai_conversations (user_id);
CREATE INDEX IF NOT EXISTS ix_ai_conversations_notebook_id
    ON ai_conversations (notebook_id);
CREATE INDEX IF NOT EXISTS ix_ai_conversations_cell_id
    ON ai_conversations (cell_id);
CREATE INDEX IF NOT EXISTS ix_ai_conversations_session_id
    ON ai_conversations (session_id);
CREATE INDEX IF NOT EXISTS ix_ai_conversations_conversation_session_id
    ON ai_conversations (conversation_session_id);
CREATE INDEX IF NOT EXISTS ix_ai_conversations_role
    ON ai_conversations (role);
CREATE INDEX IF NOT EXISTS ix_ai_conversations_created_at
    ON ai_conversations (created_at);

-- ------------------------------------------------------------
-- 11. AUDIT LOGS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_logs (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER,
    entity_type VARCHAR(50) NOT NULL,
    entity_id   INTEGER NOT NULL,
    action      VARCHAR(50) NOT NULL,
    old_data    JSON,
    new_data    JSON,
    created_at  TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id
    ON audit_logs (user_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_action
    ON audit_logs (action);

COMMIT;

-- ------------------------------------------------------------
-- VERIFICACAO RAPIDA
-- ------------------------------------------------------------
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE'
  AND table_name IN (
    'users',
    'notebooks',
    'datasets',
    'cells',
    'executions',
    'cell_cache',
    'cell_dependencies',
    'cell_versions',
    'ai_conversation_sessions',
    'ai_conversations',
    'audit_logs'
  )
ORDER BY table_name;
