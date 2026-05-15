-- ==========================================
-- DeepSeek Monitor - SQLite 数据库初始化脚本
-- © 2026 sxyubai
-- ==========================================
-- 数据库文件由应用自动创建于:
--   %LOCALAPPDATA%\DeepSeekMonitor\usage.db
-- 此脚本仅作 DDL 参考和版本追踪使用
-- ==========================================

-- 单次 API 调用记录表
CREATE TABLE IF NOT EXISTS usage_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    model           TEXT    NOT NULL DEFAULT 'deepseek-chat',
    prompt_tokens   INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens    INTEGER NOT NULL DEFAULT 0,
    cost            REAL    NOT NULL DEFAULT 0.0,
    request_type    TEXT    NOT NULL DEFAULT 'chat'
);

-- 每日用量汇总表
CREATE TABLE IF NOT EXISTS daily_stats (
    date                   TEXT PRIMARY KEY,
    total_prompt_tokens    INTEGER NOT NULL DEFAULT 0,
    total_completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens           INTEGER NOT NULL DEFAULT 0,
    total_cost             REAL    NOT NULL DEFAULT 0.0,
    request_count          INTEGER NOT NULL DEFAULT 0
);

-- 索引：按时间查询优化
CREATE INDEX IF NOT EXISTS idx_records_timestamp
    ON usage_records(timestamp);

-- 索引：按模型查询优化
CREATE INDEX IF NOT EXISTS idx_records_model
    ON usage_records(model);
