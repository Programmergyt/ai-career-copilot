-- ============================================================
-- AI Career Copilot — 建库与建表（幂等，可重复执行）
-- 在 MySQL 8.0+ 服务器上执行
-- ============================================================

-- 1. 创建数据库（如不存在）
CREATE DATABASE IF NOT EXISTS ai_career_copilot
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE ai_career_copilot;

-- 2. 会话表
CREATE TABLE IF NOT EXISTS sessions (
    session_id  VARCHAR(64)  PRIMARY KEY,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    status      ENUM('active', 'archived') NOT NULL DEFAULT 'active',
    INDEX idx_sessions_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. JD 表
CREATE TABLE IF NOT EXISTS jobs (
    id          VARCHAR(64)  PRIMARY KEY,
    session_id  VARCHAR(64)  NOT NULL,
    version     INT          NOT NULL DEFAULT 1,
    data        JSON         NOT NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_jobs_session (session_id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. 候选人画像表
CREATE TABLE IF NOT EXISTS candidate_profiles (
    id          VARCHAR(64)  PRIMARY KEY,
    session_id  VARCHAR(64)  NOT NULL,
    version     INT          NOT NULL DEFAULT 1,
    data        JSON         NOT NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_profiles_session (session_id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. 简历内容表
CREATE TABLE IF NOT EXISTS resume_contents (
    id            VARCHAR(64)  PRIMARY KEY,
    session_id    VARCHAR(64)  NOT NULL,
    version       INT          NOT NULL DEFAULT 1,
    data          JSON         NOT NULL,
    content_hash  VARCHAR(64)  NOT NULL DEFAULT '',
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_resume_contents_session (session_id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. 渲染配置表
CREATE TABLE IF NOT EXISTS render_configs (
    id          VARCHAR(64)  PRIMARY KEY,
    session_id  VARCHAR(64)  NOT NULL,
    version     INT          NOT NULL DEFAULT 1,
    data        JSON         NOT NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_render_configs_session (session_id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. HTML 快照表
CREATE TABLE IF NOT EXISTS resume_htmls (
    id                           VARCHAR(64)  PRIMARY KEY,
    session_id                   VARCHAR(64)  NOT NULL,
    version                      INT          NOT NULL DEFAULT 1,
    html                         LONGTEXT     NOT NULL,
    derived_from_content_version INT          NOT NULL DEFAULT 1,
    derived_from_render_version  INT          NOT NULL DEFAULT 1,
    checksum                     VARCHAR(64)  NOT NULL DEFAULT '',
    created_at                   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_resume_htmls_session (session_id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. 面试问答表
CREATE TABLE IF NOT EXISTS interview_qas (
    id          VARCHAR(64)  PRIMARY KEY,
    session_id  VARCHAR(64)  NOT NULL,
    version     INT          NOT NULL DEFAULT 1,
    data        JSON         NOT NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_interview_qas_session (session_id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 9. 事件流表
CREATE TABLE IF NOT EXISTS conversation_events (
    event_id           VARCHAR(64)  PRIMARY KEY,
    session_id         VARCHAR(64)  NOT NULL,
    message_id         VARCHAR(64)  NOT NULL,
    intent             VARCHAR(32)  NOT NULL,
    triggered_agents   JSON         NOT NULL,
    state_diff_summary JSON         DEFAULT NULL,
    status             ENUM('success', 'failed', 'partial') NOT NULL DEFAULT 'success',
    created_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_events_session (session_id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 10. 记忆记录表（长期记忆真值来源）
CREATE TABLE IF NOT EXISTS memory_records (
    memory_id        VARCHAR(64)  PRIMARY KEY,
    user_id          VARCHAR(64)  NULL,
    session_id       VARCHAR(64)  NULL,
    scope            ENUM('session', 'user', 'global') NOT NULL DEFAULT 'session',
    kind             VARCHAR(32)  NOT NULL,
    content          TEXT         NOT NULL,
    data             JSON         NOT NULL,
    source           JSON         NOT NULL,
    confidence       DECIMAL(5,4) NOT NULL DEFAULT 1.0000,
    status           ENUM('active', 'pending', 'archived', 'deleted') NOT NULL DEFAULT 'active',
    content_hash     VARCHAR(64)  NOT NULL DEFAULT '',
    embedding_status ENUM('pending', 'indexed', 'failed') NOT NULL DEFAULT 'pending',
    created_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    expires_at       DATETIME     NULL,
    INDEX idx_memory_owner (user_id, session_id),
    INDEX idx_memory_session (session_id),
    INDEX idx_memory_kind_status (kind, status),
    INDEX idx_memory_hash (content_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 11. 记忆事件表（记忆写入/删除审计）
CREATE TABLE IF NOT EXISTS memory_events (
    event_id   VARCHAR(64) PRIMARY KEY,
    user_id    VARCHAR(64) NULL,
    session_id VARCHAR(64) NULL,
    event_type VARCHAR(32) NOT NULL,
    memory_id  VARCHAR(64) NULL,
    payload    JSON        NOT NULL,
    created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_memory_events_owner (user_id, session_id),
    INDEX idx_memory_events_memory (memory_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 12. 记忆摘要表（长期摘要缓存，可由后台任务刷新）
CREATE TABLE IF NOT EXISTS memory_summaries (
    summary_id        VARCHAR(64) PRIMARY KEY,
    user_id           VARCHAR(64) NULL,
    session_id        VARCHAR(64) NULL,
    scope             ENUM('session', 'user', 'global') NOT NULL DEFAULT 'session',
    summary           TEXT        NOT NULL,
    source_memory_ids JSON        NOT NULL,
    created_at        DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_memory_summaries_owner (user_id, session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
