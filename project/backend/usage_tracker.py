"""
本地用量追踪器
使用 SQLite 持久化存储 API 调用记录和 Token 消耗统计
"""

import sqlite3
import os
import json
from datetime import datetime, date
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
    request_type: str = "chat"  # chat / reasoner


class UsageTracker:
    """用量追踪器 - 线程安全 + SQLite 持久化"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # 默认存储在用户数据目录
            app_data_dir = os.path.join(
                os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                "DeepSeekMonitor"
            )
            os.makedirs(app_data_dir, exist_ok=True)
            db_path = os.path.join(app_data_dir, "usage.db")

        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接（每次调用创建新连接，避免多线程问题）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=3000")
        return conn

    def _init_db(self):
        """初始化数据库表结构"""
        conn = self._get_conn()
        try:
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
                    last_balance REAL NOT NULL DEFAULT 0.0
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def record_usage(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost: float,
        request_type: str = "chat",
    ) -> int:
        """记录一次 API 调用"""
        total_tokens = prompt_tokens + completion_tokens
        today = date.today().isoformat()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """INSERT INTO usage_records
                   (timestamp, model, prompt_tokens, completion_tokens, total_tokens, cost, request_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (now, model, prompt_tokens, completion_tokens, total_tokens, cost, request_type),
            )
            record_id = cursor.lastrowid

            # 更新今日统计
            conn.execute(
                """INSERT INTO daily_stats (date, total_prompt_tokens, total_completion_tokens,
                   total_tokens, total_cost, request_count)
                   VALUES (?, ?, ?, ?, ?, 1)
                   ON CONFLICT(date) DO UPDATE SET
                   total_prompt_tokens = total_prompt_tokens + ?,
                   total_completion_tokens = total_completion_tokens + ?,
                   total_tokens = total_tokens + ?,
                   total_cost = total_cost + ?,
                   request_count = request_count + 1""",
                (today, prompt_tokens, completion_tokens, total_tokens, cost,
                 prompt_tokens, completion_tokens, total_tokens, cost),
            )
            conn.commit()
            return record_id
        finally:
            conn.close()

    def get_today_stats(self) -> Dict[str, Any]:
        """获取今日用量统计"""
        today = date.today().isoformat()
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM daily_stats WHERE date = ?", (today,)
            ).fetchone()
            if row:
                return {
                    "date": row["date"],
                    "total_prompt_tokens": row["total_prompt_tokens"],
                    "total_completion_tokens": row["total_completion_tokens"],
                    "total_tokens": row["total_tokens"],
                    "total_cost": round(row["total_cost"], 6),
                    "request_count": row["request_count"],
                }
            return {
                "date": today,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "request_count": 0,
            }
        finally:
            conn.close()

    def update_daily_balance(self, current_balance: float) -> float:
        """
        更新当日余额追踪，返回今日消耗（基于余额差额）。
        逻辑：
        - 当天首次 → max_balance = current_balance，消耗 = 0
        - 余额下降 → 消耗 = max_balance - current_balance
        - 余额上升（充值）→ 更新 max_balance，消耗 = 0（重新计数）
        """
        today = date.today().isoformat()
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT max_balance, last_balance FROM daily_balance WHERE date = ?",
                (today,)
            ).fetchone()

            if row is None:
                # 当天首次记录
                max_bal = current_balance
                consumption = 0.0
                conn.execute(
                    "INSERT INTO daily_balance (date, max_balance, last_balance) VALUES (?, ?, ?)",
                    (today, max_bal, current_balance)
                )
            else:
                last_max = row["max_balance"]
                if current_balance > last_max:
                    # 充值 or 余额增加 → 更新最大值，消耗归零
                    max_bal = current_balance
                    consumption = 0.0
                    conn.execute(
                        "UPDATE daily_balance SET max_balance = ?, last_balance = ? WHERE date = ?",
                        (max_bal, current_balance, today)
                    )
                else:
                    # 余额正常下降 → 消耗 = max - current
                    max_bal = last_max
                    consumption = round(max_bal - current_balance, 6)
                    conn.execute(
                        "UPDATE daily_balance SET last_balance = ? WHERE date = ?",
                        (current_balance, today)
                    )

            conn.commit()
            return consumption
        finally:
            conn.close()

    def get_daily_consumption(self) -> float:
        """获取今日基于余额的消耗（只读，不修改数据）"""
        today = date.today().isoformat()
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT max_balance, last_balance FROM daily_balance WHERE date = ?",
                (today,)
            ).fetchone()
            if row is None:
                return 0.0
            consumption = round(row["max_balance"] - row["last_balance"], 6)
            return max(0.0, consumption)  # 安全兜底，确保不为负
        finally:
            conn.close()

    def get_weekly_stats(self) -> Dict[str, Any]:
        """获取本周用量统计"""
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
        """获取本月用量统计"""
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
        """获取最近的调用记录"""
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
        """获取全部历史统计"""
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
