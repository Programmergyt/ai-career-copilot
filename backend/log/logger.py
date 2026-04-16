"""统一日志配置。

日志按类别分文件存储在 log/ 目录下：
  - app.log        — 应用主日志
  - agent.log      — Agent 调用日志
  - api.log        — API 请求/响应日志
  - storage.log    — 数据库（MySQL / Redis）操作日志
  - error.log      — ERROR 及以上级别（所有来源）

同时在控制台输出 INFO 及以上级别。
"""

import logging
import sys
from pathlib import Path

_LOG_DIR = Path(__file__).parent
_INITIALIZED = False

_FMT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.DEBUG) -> None:
    """初始化全局日志系统（只执行一次）。"""
    global _INITIALIZED
    if _INITIALIZED:
        return
    _INITIALIZED = True

    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(_FMT, datefmt=_DATE_FMT)

    root = logging.getLogger()
    root.setLevel(level)

    # 控制台 handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    root.addHandler(console)

    # 分类文件 handlers
    _categories = {
        "app": logging.DEBUG,
        "agent": logging.DEBUG,
        "api": logging.DEBUG,
        "storage": logging.DEBUG,
    }
    for name, lvl in _categories.items():
        fh = logging.FileHandler(_LOG_DIR / f"{name}.log", encoding="utf-8")
        fh.setLevel(lvl)
        fh.setFormatter(formatter)
        logging.getLogger(name).addHandler(fh)

    # error.log 收集所有 ERROR+
    err_handler = logging.FileHandler(_LOG_DIR / "error.log", encoding="utf-8")
    err_handler.setLevel(logging.ERROR)
    err_handler.setFormatter(formatter)
    root.addHandler(err_handler)


def get_logger(category: str = "app") -> logging.Logger:
    """获取指定分类的 logger。

    Args:
        category: 日志分类名，对应 log/<category>.log。
                  预定义分类: app, agent, api, storage。
    """
    return logging.getLogger(category)
