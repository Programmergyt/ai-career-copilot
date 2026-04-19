"""AI Career Copilot 后端入口。"""

from pathlib import Path
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config_loader import get_fastapi_config
from log import setup_logging, get_logger
from api.chat import router as chat_router
from api.resume import router as resume_router
from api.export import router as export_router
from storage.mysql_client import get_mysql_pool
from storage.redis_client import get_redis_client

# 初始化日志
setup_logging()
logger = get_logger("app")
BACKEND_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="AI Career Copilot",
    description="多 Agent 求职辅助系统",
    version="0.1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat_router)
app.include_router(resume_router)
app.include_router(export_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


def _check_mysql_connection() -> None:
    """启动前检查 MySQL 连通性。"""
    conn = get_mysql_pool().connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
    finally:
        conn.close()

    value = row.get("1") if isinstance(row, dict) else row[0] if row else None
    if value != 1:
        raise RuntimeError("MySQL 连通性检查失败：SELECT 1 未返回预期结果")


def _check_redis_connection() -> None:
    """启动前检查 Redis 连通性。"""
    client = get_redis_client()
    if not client.ping():
        raise RuntimeError("Redis 连通性检查失败：PING 未返回成功")


def _check_required_services() -> None:
    """在启动服务前验证关键依赖是否可用。"""
    logger.info("Checking MySQL connectivity before startup")
    _check_mysql_connection()
    logger.info("MySQL connectivity check passed")

    logger.info("Checking Redis connectivity before startup")
    _check_redis_connection()
    logger.info("Redis connectivity check passed")


if __name__ == "__main__":
    cfg = get_fastapi_config()
    try:
        _check_required_services()
    except Exception as exc:  # noqa: BLE001
        logger.critical("Startup aborted because dependency check failed: %s", exc, exc_info=True)
        sys.exit(1)

    logger.info("Starting AI Career Copilot server on %s:%s", cfg["host"], cfg["port"])
    uvicorn.run(
        "main:app",
        app_dir=str(BACKEND_DIR),
        host=cfg["host"],
        port=cfg["port"],
        reload=cfg.get("debug", False),
    )
