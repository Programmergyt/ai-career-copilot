"""AI Career Copilot 后端入口。"""

from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config_loader import get_fastapi_config
from log import setup_logging, get_logger
from api.chat import router as chat_router
from api.resume import router as resume_router
from api.export import router as export_router

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


if __name__ == "__main__":
    cfg = get_fastapi_config()
    logger.info("Starting AI Career Copilot server on %s:%s", cfg["host"], cfg["port"])
    uvicorn.run(
        "main:app",
        app_dir=str(BACKEND_DIR),
        host=cfg["host"],
        port=cfg["port"],
        reload=cfg.get("debug", False),
    )
