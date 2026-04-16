# 示例: 在项目根目录执行 python backend/sql/init_db.py
"""执行 init_schema.sql 在 MySQL 服务器上初始化数据库和表结构。

依赖 backend/config.yaml 中的 mysql 配置（host, port, user, password）。
注意：连接时不指定 database，因为 SQL 脚本中包含 CREATE DATABASE。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 确保 backend 目录在 sys.path 中，便于导入 config_loader。
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import pymysql

from config_loader import get_mysql_config

_SQL_FILE = Path(__file__).parent / "init_schema.sql"


def run_init_schema() -> None:
    """读取 init_schema.sql 并逐条执行。"""
    cfg = get_mysql_config()

    if not _SQL_FILE.exists():
        print(f"[ERROR] SQL 文件不存在: {_SQL_FILE}")
        sys.exit(1)

    sql_text = _SQL_FILE.read_text(encoding="utf-8")

    # 按分号拆分语句，过滤空白和纯注释
    statements = [s.strip() for s in sql_text.split(";") if s.strip()]
    statements = [s for s in statements if not _is_comment_only(s)]

    print(f"[INFO] 连接 MySQL {cfg['host']}:{cfg['port']} (user={cfg['user']})")

    connection = pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        charset=cfg.get("charset", "utf8mb4"),
        # 不指定 database，由 SQL 脚本中的 USE 语句切换
        autocommit=True,
    )

    try:
        with connection.cursor() as cursor:
            for i, stmt in enumerate(statements, 1):
                try:
                    cursor.execute(stmt)
                    print(f"  [{i}/{len(statements)}] OK")
                except pymysql.Error as e:
                    print(f"  [{i}/{len(statements)}] WARN: {e}")
        print("[INFO] 数据库初始化完成。")
    finally:
        connection.close()


def _is_comment_only(sql: str) -> bool:
    """判断 SQL 片段是否只包含注释和空行。"""
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("--"):
            return False
    return True


if __name__ == "__main__":
    run_init_schema()
