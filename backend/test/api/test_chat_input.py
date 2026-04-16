"""chat_input 模块测试。"""
# 示例: 在项目根目录执行 pytest backend/test/api/test_chat_input.py -sv
from __future__ import annotations

import base64

import pytest
from fastapi import HTTPException

from api.chat_input import prepare_chat_input


class TestPrepareChatInput:

    def test_prepare_chat_input_appends_attachment_text(self):
        prepared = prepare_chat_input(
            "请帮我优化这份简历",
            [{"filename": "profile.md", "content": "# 张三\n熟悉 LangGraph", "encoding": "text"}],
        )

        assert "请帮我优化这份简历" in prepared.user_message
        assert "[附件 1] 文件名: profile.md" in prepared.user_message
        assert "熟悉 LangGraph" in prepared.user_message
        assert prepared.user_attachments[0]["filename"] == "profile.md"
        assert prepared.user_attachments[0]["parsed_text"].startswith("# 张三")

    def test_prepare_chat_input_supports_base64_text_payload(self):
        payload = base64.b64encode("岗位要求\n熟悉 Python".encode("utf-8")).decode("ascii")

        prepared = prepare_chat_input(
            "",
            [{"name": "jd.txt", "content": payload, "encoding": "base64"}],
        )

        assert "用户本轮没有额外文字说明" in prepared.user_message
        assert "岗位要求" in prepared.user_message
        assert prepared.user_attachments[0]["suffix"] == ".txt"

    def test_prepare_chat_input_auto_detects_base64_text_payload(self):
        payload = base64.b64encode("项目经历\n多 Agent 协作".encode("utf-8")).decode("ascii")

        prepared = prepare_chat_input(
            "",
            [{"name": "profile.md", "content": payload}],
        )

        assert "多 Agent 协作" in prepared.user_message
        assert prepared.user_attachments[0]["content_encoding"] == "auto"

    def test_prepare_chat_input_auto_keeps_plain_ascii_text(self):
        prepared = prepare_chat_input(
            "",
            [{"name": "notes.md", "content": "test"}],
        )

        assert "以下为附件解析文本:\ntest" in prepared.user_message
        assert prepared.user_attachments[0]["parsed_text"] == "test"

    def test_prepare_chat_input_rejects_unsupported_suffix(self):
        with pytest.raises(HTTPException) as exc_info:
            prepare_chat_input("test", [{"filename": "notes.xlsx", "content": "data", "encoding": "text"}])

        assert exc_info.value.status_code == 400
        assert "仅支持" in exc_info.value.detail

    def test_prepare_chat_input_requires_attachment_content(self):
        with pytest.raises(HTTPException) as exc_info:
            prepare_chat_input("test", [{"filename": "notes.md"}])

        assert exc_info.value.status_code == 400
        assert "缺少内容" in exc_info.value.detail