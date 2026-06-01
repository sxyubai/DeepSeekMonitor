"""本地用量追踪器
使用 SQLite 持久化存储 API 调用记录和 Token 消耗统计
"""

import sqlite3
import os
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict


@dataclass
class UsageRecord:
    """单次 API 调用记录"""
    id: int = 0
    timestamp: str = ""
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    request_type: str = "chat"


class UsageTracker:
    """用量追踪器 - 线程安全 + SQLite 持久化"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            app_data_dir = os.path.join(
                os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                "DeepSeekMonitor"
            )
            os.makedirs(app_data_dir, exist_ok=True)
            db_path = os.path.join(app_data_dir, "usage.db")
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=3000")
        return conn

    def _init_db(self):
        """初始化数据库表结构"""
        conn = self._get_conn()
        try:
            # Migration: ensure total_consumption column exists first
            try:
                conn.execute("ALTER TABLE daily_balance ADD COLUMN total_consumption REAL NOT NULL DEFAULT 0.0")
                conn.commit()
            except Exception:
                pass

            try:
                conn.execute("""
                    UPDATE daily_balance
                    SET total_consumption = ROUND(MAX(max_balance,0) - MIN(last_balance,0), 6)
                    WHERE total_consumption = 0 AND max_balance > last_balance
                """)
                conn.commit()
            except Exception:
                pass

            conn.executescript("""
                CREATE TABLE IF NOT EXISTS usage_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    model TEXT NOT NULL DEFAULT 'deepseek-chat',
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    cost REAL NOT NULL DEFAULT 0.0,
                    request_type TEXT NOT NULL DEFAULT 'chat'
                );

                CREATE TABLE IF NOT EXISTS daily_stats (
                    date TEXT PRIMARY KEY,
                    total_prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    total_completion_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    total_cost REAL NOT NULL DEFAULT 0.0,
                    request_count INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_records_timestamp
                    ON usage_records(timestamp);

                CREATE TABLE IF NOT EXISTS daily_balance (
                    date TEXT PRIMARY KEY,
                    max_balance REAL NOT NULL DEFAULT 0.0,
                    last_balance REAL NOT NULL DEFAULT 0.0,
                    total_consumption REAL NOT NULL DEFAULT 0.0
                );

                CREATE TABLE IF NOT EXISTS period_config (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    start_balance REAL NOT NULL DEFAULT 0.0,
                    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def record_usage(self, model, prompt_tokens, completion_tokens, cost, request_type="chat"):
        total_tokens = prompt_tokens + completion_tokens
        today = date.today().isoformat()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO usage_records (timestamp, model, prompt_tokens, completion_tokens, total_tokens, cost, request_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (now, model, prompt_tokens, completion_tokens, total_tokens, cost, request_type),
            )

            row = conn.execute(
                "SELECT total_prompt_tokens, total_completion_tokens, total_tokens, total_cost, request_count FROM daily_stats WHERE date = ?",
                (today,)
            ).fetchone()

            if row is None:
                conn.execute(
                    "INSERT INTO daily_stats (date, total_prompt_tokens, total_completion_tokens, total_tokens, total_cost, request_count) VALUES (?, ?, ?, ?, ?, 1)",
                    (today, prompt_tokens, completion_tokens, total_tokens, cost),
                )
            else:
                conn.execute(
                    "UPDATE daily_stats SET total_prompt_tokens = total_prompt_tokens + ?, total_completion_tokens = total_completion_tokens + ?, total_tokens = total_tokens + ?, total_cost = total_cost + ?, request_count = request_count + 1 WHERE date = ?",
                    (prompt_tokens, completion_tokens, total_tokens, cost, today),
                )

            conn.commit()
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        finally:
            conn.close()

    def update_daily_balance(self, balance: float) -> float:
        """更新每日余额并计算今日消耗（基于余额差额）"""
        today = date.today().isoformat()
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT max_balance, last_balance, total_consumption FROM daily_balance WHERE date = ?",
                (today,)
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO daily_balance (date, max_balance, last_balance, total_consumption) VALUES (?, ?, ?, 0.0)",
                    (today, balance, balance),
                )
                conn.commit()
                return 0.0
            else:
                prev_max = row["max_balance"]
                new_max = max(prev_max, balance)
                consumption = round(new_max - balance, 6)
                if consumption < 0:
                    consumption = 0.0
                conn.execute(
                    "UPDATE daily_balance SET max_balance = ?, last_balance = ?, total_consumption = ? WHERE date = ?",
                    (new_max, balance, consumption, today),
                )
                conn.commit()
                return consumption
        finally:
            conn.close()

    def get_balance_history(self, days: int = 7) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            limit_date = (date.today() - timedelta(days=days)).isoformat()
            rows = conn.execute(
                "SELECT date, max_balance, last_balance, total_consumption FROM daily_balance WHERE date >= ? ORDER BY date",
                (limit_date,)
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_all_balance_records(self) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT date, total_consumption, max_balance, last_balance FROM daily_balance ORDER BY date DESC"
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_daily_consumption(self) -> float:
        today = date.today().isoformat()
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT total_consumption FROM daily_balance WHERE date = ?",
                (today,)
            ).fetchone()
            if row is None:
                return 0.0
            return max(0.0, row["total_consumption"])
        finally:
            conn.close()

    def reset_period(self, current_balance: float):
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT id FROM period_config WHERE id = 1").fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO period_config (id, start_balance) VALUES (1, ?)",
                    (current_balance,)
                )
            else:
                conn.execute(
                    "UPDATE period_config SET start_balance = ?, updated_at = datetime('now','localtime') WHERE id = 1",
                    (current_balance,)
                )
            conn.commit()
        finally:
            conn.close()

    def is_period_initialized(self) -> bool:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT id FROM period_config WHERE id = 1").fetchone()
            return row is not None
        finally:
            conn.close()

    def get_period_consumption(self, current_balance: float) -> float:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT start_balance FROM period_config WHERE id = 1"
            ).fetchone()
            if row is None:
                return 0.0
            consumption = round(row["start_balance"] - current_balance, 6)
            return max(0.0, consumption)
        finally:
            conn.close()

    def get_weekly_stats(self) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            row = conn.execute("""
                SELECT
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(total_cost), 0) as total_cost,
                    COALESCE(SUM(request_count), 0) as request_count
                FROM daily_stats
                WHERE date >= date('now', 'weekday 0', '-7 days')
            """).fetchone()
            return {
                "total_tokens": row["total_tokens"],
                "total_cost": round(row["total_cost"], 6),
                "request_count": row["request_count"],
            }
        finally:
            conn.close()

    def get_monthly_stats(self) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            today = date.today()
            first_day = today.replace(day=1).isoformat()
            row = conn.execute("""
                SELECT
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(total_cost), 0) as total_cost,
                    COALESCE(SUM(request_count), 0) as request_count
                FROM daily_stats
                WHERE date >= ?
            """, (first_day,)).fetchone()
            return {
                "total_tokens": row["total_tokens"],
                "total_cost": round(row["total_cost"], 6),
                "request_count": row["request_count"],
            }
        finally:
            conn.close()

    def get_recent_records(self, limit: int = 20) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM usage_records ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_all_time_stats(self) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            row = conn.execute("""
                SELECT
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(total_cost), 0) as total_cost,
                    COALESCE(SUM(request_count), 0) as request_count
                FROM daily_stats
            """).fetchone()
            return {
                "total_tokens": row["total_tokens"],
                "total_cost": round(row["total_cost"], 6),
                "request_count": row["request_count"],
            }
        finally:
            conn.close()
