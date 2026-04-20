"""MySQL 客户端封装：基于 aiomysql 的异步持久化存储。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import aiomysql

from config_loader import get_mysql_config
from log import get_logger

logger = get_logger("storage")

_pool: aiomysql.Pool | None = None


async def get_mysql_pool() -> aiomysql.Pool:
    """获取 MySQL 异步连接池（单例）。"""
    global _pool
    if _pool is None:
        cfg = get_mysql_config()
        _pool = await aiomysql.create_pool(
            host=cfg["host"],
            port=cfg["port"],
            user=cfg["user"],
            password=cfg["password"],
            db=cfg["database"],
            charset=cfg.get("charset", "utf8mb4"),
            maxsize=cfg.get("pool_size", 5),
            autocommit=False,
            cursorclass=aiomysql.DictCursor,
        )
        logger.info("MySQL async pool initialized: %s:%s/%s", cfg["host"], cfg["port"], cfg["database"])
    return _pool


class MySQLStore:
    """MySQL 异步持久化操作封装。"""

    def __init__(self, pool: aiomysql.Pool) -> None:
        self._pool = pool

    # ---- sessions ----
    async def upsert_session(self, session_id: str, status: str = "active") -> None:
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        sql = """
            INSERT INTO sessions (session_id, created_at, updated_at, status)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE updated_at = %s, status = %s
        """
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (session_id, now, now, status, now, status))
            await conn.commit()
        logger.debug("Upserted session %s", session_id)

    # ---- generic JSON table helpers ----
    async def _upsert_json(self, table: str, row_id: str, session_id: str, data: dict, version: int = 1,
                           extra_cols: dict | None = None) -> None:
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        json_str = json.dumps(data, ensure_ascii=False, default=str)
        extra_col_names = ""
        extra_placeholders = ""
        extra_update = ""
        extra_vals: list = []
        if extra_cols:
            for k, v in extra_cols.items():
                extra_col_names += f", {k}"
                extra_placeholders += ", %s"
                extra_update += f", {k} = %s"
                extra_vals.append(v)

        sql = f"""
            INSERT INTO {table} (id, session_id, version, data{extra_col_names}, created_at, updated_at)
            VALUES (%s, %s, %s, %s{extra_placeholders}, %s, %s)
            ON DUPLICATE KEY UPDATE version = %s, data = %s{extra_update}, updated_at = %s
        """
        vals = [row_id, session_id, version, json_str, *extra_vals, now, now,
                version, json_str, *extra_vals, now]
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, vals)
            await conn.commit()
        logger.debug("Upserted %s id=%s session=%s v=%s", table, row_id, session_id, version)

    async def _get_json(self, table: str, row_id: str) -> dict | None:
        sql = f"SELECT data, version FROM {table} WHERE id = %s"
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (row_id,))
                row = await cur.fetchone()
        if row is None:
            return None
        data = row["data"]
        if isinstance(data, str):
            data = json.loads(data)
        return data

    async def _get_by_session(self, table: str, session_id: str) -> dict | None:
        sql = f"SELECT data, version FROM {table} WHERE session_id = %s ORDER BY updated_at DESC LIMIT 1"
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (session_id,))
                row = await cur.fetchone()
        if row is None:
            return None
        data = row["data"]
        if isinstance(data, str):
            data = json.loads(data)
        return data

    # ---- typed helpers ----
    async def save_job(self, row_id: str, session_id: str, data: dict, version: int = 1) -> None:
        await self._upsert_json("jobs", row_id, session_id, data, version)

    async def get_job(self, session_id: str) -> dict | None:
        return await self._get_by_session("jobs", session_id)

    async def save_candidate_profile(self, row_id: str, session_id: str, data: dict) -> None:
        await self._upsert_json("candidate_profiles", row_id, session_id, data)

    async def get_candidate_profile(self, session_id: str) -> dict | None:
        return await self._get_by_session("candidate_profiles", session_id)

    async def save_resume_content(self, row_id: str, session_id: str, data: dict, version: int = 1,
                                  content_hash: str = "") -> None:
        await self._upsert_json("resume_contents", row_id, session_id, data, version,
                                extra_cols={"content_hash": content_hash})

    async def get_resume_content(self, session_id: str) -> dict | None:
        return await self._get_by_session("resume_contents", session_id)

    async def save_render_config(self, row_id: str, session_id: str, data: dict, version: int = 1) -> None:
        await self._upsert_json("render_configs", row_id, session_id, data, version)

    async def get_render_config(self, session_id: str) -> dict | None:
        return await self._get_by_session("render_configs", session_id)

    async def save_resume_html(self, row_id: str, session_id: str, html: str, version: int = 1,
                               content_ver: int = 1, render_ver: int = 1, checksum: str = "") -> None:
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        sql = """
            INSERT INTO resume_htmls (id, session_id, version, html, derived_from_content_version,
                                      derived_from_render_version, checksum, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE version = %s, html = %s, derived_from_content_version = %s,
                                    derived_from_render_version = %s, checksum = %s
        """
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (row_id, session_id, version, html, content_ver, render_ver, checksum, now,
                                        version, html, content_ver, render_ver, checksum))
            await conn.commit()

    async def save_interview_qa(self, row_id: str, session_id: str, data: dict, version: int = 1) -> None:
        await self._upsert_json("interview_qas", row_id, session_id, data, version)

    async def save_event(self, event: dict) -> None:
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        sql = """
            INSERT INTO conversation_events
                (event_id, session_id, message_id, intent, triggered_agents, state_diff_summary, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE status = %s
        """
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (
                    event["event_id"], event["session_id"], event["message_id"],
                    event["intent"],
                    json.dumps(event.get("triggered_agents", []), ensure_ascii=False),
                    json.dumps(event.get("state_diff_summary", {}), ensure_ascii=False),
                    event["status"], now,
                    event["status"],
                ))
            await conn.commit()
