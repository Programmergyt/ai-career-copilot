"""长期记忆 — SQLite 存储用户偏好与历史"""

import json
import sqlite3
import os
from pathlib import Path
from datetime import datetime, timezone


DB_PATH = "./data/long_term_memory.db"


def _get_conn(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: str | None = None, reset: bool = False) -> None:
    """初始化长期记忆数据库表结构。"""
    path = db_path or DB_PATH

    # 如果需要重置数据库
    if reset and os.path.exists(path):
        os.remove(path)

    conn = _get_conn(path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jd_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jd_text TEXT NOT NULL,
            analysis_json TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS resume_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jd_id INTEGER,
            resume_content TEXT NOT NULL,
            check_result_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (jd_id) REFERENCES jd_history(id)
        );

        CREATE TABLE IF NOT EXISTS user_preferences (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


def save_jd(jd_text: str, analysis: dict, db_path: str | None = None) -> int:
    """保存 JD 分析记录，返回 id。"""
    conn = _get_conn(db_path)
    cur = conn.execute(
        "INSERT INTO jd_history (jd_text, analysis_json, created_at) VALUES (?, ?, ?)",
        (jd_text, json.dumps(analysis, ensure_ascii=False), _now()),
    )
    conn.commit()
    jd_id = cur.lastrowid
    conn.close()
    return jd_id


def save_resume(
    jd_id: int,
    resume_content: str,
    check_result: dict | None = None,
    db_path: str | None = None,
) -> int:
    """保存简历版本，返回 id。"""
    conn = _get_conn(db_path)
    cur = conn.execute(
        "INSERT INTO resume_history (jd_id, resume_content, check_result_json, created_at) VALUES (?, ?, ?, ?)",
        (
            jd_id,
            resume_content,
            json.dumps(check_result, ensure_ascii=False) if check_result else None,
            _now(),
        ),
    )
    conn.commit()
    resume_id = cur.lastrowid
    conn.close()
    return resume_id


def get_preference(key: str, default: str | None = None, db_path: str | None = None) -> str | None:
    conn = _get_conn(db_path)
    row = conn.execute(
        "SELECT value FROM user_preferences WHERE key = ?", (key,)
    ).fetchone()
    conn.close()
    return row[0] if row else default


def set_preference(key: str, value: str, db_path: str | None = None) -> None:
    conn = _get_conn(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO user_preferences (key, value, updated_at) VALUES (?, ?, ?)",
        (key, value, _now()),
    )
    conn.commit()
    conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
