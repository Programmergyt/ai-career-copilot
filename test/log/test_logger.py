# python -m pytest -sv test/test_logger.py
"""日志模块单元测试。"""

import logging
import pytest
from pathlib import Path

from log import setup_logging, get_logger


class TestSetupLogging:

    def test_setup_logging_idempotent(self):
        """setup_logging 可多次调用不报错。"""
        setup_logging()
        setup_logging()  # 第二次调用不应出错

    def test_get_logger_returns_logger(self):
        logger = get_logger("app")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "app"

    def test_get_logger_different_categories(self):
        app_logger = get_logger("app")
        agent_logger = get_logger("agent")
        api_logger = get_logger("api")
        storage_logger = get_logger("storage")

        assert app_logger.name == "app"
        assert agent_logger.name == "agent"
        assert api_logger.name == "api"
        assert storage_logger.name == "storage"

    def test_get_logger_default_category(self):
        logger = get_logger()
        assert logger.name == "app"

    def test_logger_can_log(self):
        """确保 logger 能正常写入日志不报错。"""
        setup_logging()
        logger = get_logger("app")
        logger.info("单元测试日志写入")
        logger.debug("Debug 级别测试")
        logger.warning("Warning 级别测试")
