# 示例: 在项目根目录执行 pytest backend/test/sql/test_init_db.py -sv
# 注意：需要 MySQL 服务可用，属于集成测试
"""sql/init_db.py 初始化脚本测试。

验证 run_init_schema() 执行后数据库和表均已创建。
"""

import pytest
import pymysql

from config_loader import get_mysql_config


@pytest.fixture(scope="module")
def db_connection():
    """建立到 ai_career_copilot 数据库的连接。"""
    cfg = get_mysql_config()
    try:
        conn = pymysql.connect(
            host=cfg["host"],
            port=cfg["port"],
            user=cfg["user"],
            password=cfg["password"],
            database=cfg["database"],
            charset=cfg["charset"],
            cursorclass=pymysql.cursors.DictCursor,
        )
        yield conn
        conn.close()
    except Exception as e:
        pytest.skip(f"MySQL 不可用: {e}")


# init_schema.sql 中定义的所有表
EXPECTED_TABLES = [
    "sessions",
    "jobs",
    "candidate_profiles",
    "resume_contents",
    "render_configs",
    "resume_htmls",
    "interview_qas",
    "conversation_events",
    "memory_records",
    "memory_events",
    "memory_summaries",
]


class TestDatabaseExists:

    def test_database_exists(self, db_connection):
        with db_connection.cursor() as cur:
            cur.execute("SELECT DATABASE()")
            row = cur.fetchone()
        assert row is not None
        assert row["DATABASE()"] == "ai_career_copilot"


class TestTablesExist:

    @pytest.mark.parametrize("table_name", EXPECTED_TABLES)
    def test_table_exists(self, db_connection, table_name):
        with db_connection.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM information_schema.tables "
                "WHERE table_schema = 'ai_career_copilot' AND table_name = %s",
                (table_name,),
            )
            row = cur.fetchone()
        assert row["cnt"] == 1, f"表 {table_name} 不存在"


class TestTableStructure:

    def test_sessions_columns(self, db_connection):
        with db_connection.cursor() as cur:
            cur.execute("DESCRIBE sessions")
            columns = {row["Field"] for row in cur.fetchall()}
        assert "session_id" in columns
        assert "status" in columns
        assert "created_at" in columns

    def test_jobs_foreign_key(self, db_connection):
        """jobs 表应有指向 sessions 的外键。"""
        with db_connection.cursor() as cur:
            cur.execute(
                "SELECT REFERENCED_TABLE_NAME FROM information_schema.KEY_COLUMN_USAGE "
                "WHERE TABLE_SCHEMA = 'ai_career_copilot' AND TABLE_NAME = 'jobs' "
                "AND REFERENCED_TABLE_NAME IS NOT NULL"
            )
            refs = {row["REFERENCED_TABLE_NAME"] for row in cur.fetchall()}
        assert "sessions" in refs

    def test_resume_htmls_has_html_column(self, db_connection):
        with db_connection.cursor() as cur:
            cur.execute("DESCRIBE resume_htmls")
            columns = {row["Field"]: row["Type"] for row in cur.fetchall()}
        assert "html" in columns
        assert "longtext" in columns["html"].lower()

    def test_conversation_events_columns(self, db_connection):
        with db_connection.cursor() as cur:
            cur.execute("DESCRIBE conversation_events")
            columns = {row["Field"] for row in cur.fetchall()}
        assert "event_id" in columns
        assert "intent" in columns
        assert "triggered_agents" in columns
        assert "status" in columns
