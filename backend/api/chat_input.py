"""Chat API 输入预处理。"""

from __future__ import annotations

import base64
import binascii
import re
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

from tools.file_parser import parse_content_bytes, supported_upload_suffixes


_TEXT_SUFFIXES = {".txt", ".md"}
_ALLOWED_SUFFIXES = supported_upload_suffixes()
_MAX_PREVIEW_CHARS = 12000
_BASE64_RE = re.compile(r"^[A-Za-z0-9+/=\r\n]+$")


class PreparedChatInput(BaseModel):
    """标准化后的 Chat 输入。"""

    user_message: str
    user_attachments: list[dict[str, Any]] = Field(default_factory=list)


def prepare_chat_input(message: str, attachments: list[dict[str, Any]]) -> PreparedChatInput:
    """解析并拼接用户消息与上传附件。"""
    normalized_attachments: list[dict[str, Any]] = []
    attachment_blocks: list[str] = []

    for index, attachment in enumerate(attachments, start=1):
        normalized = _normalize_attachment(attachment, index)
        parsed_text = _parse_attachment(normalized)
        normalized["parsed_text"] = parsed_text
        normalized_attachments.append(normalized)
        attachment_blocks.append(_build_attachment_block(index, normalized["filename"], parsed_text))

    if not attachment_blocks:
        return PreparedChatInput(user_message=message, user_attachments=[])

    message = message.strip()
    prefix = message if message else "用户本轮没有额外文字说明，请优先基于附件内容完成解析。"
    instruction = (
        "以下是用户上传附件解析出的文本，请把它们视作本轮输入的一部分。"
        "若用户文字与附件内容冲突，以用户文字中的明确要求为准；"
        "若需要抽取候选人信息或岗位信息，请优先使用附件中的原始内容，不要忽略文件名提供的上下文。"
    )
    merged_message = "\n\n".join([prefix, instruction, *attachment_blocks])
    return PreparedChatInput(user_message=merged_message, user_attachments=normalized_attachments)


def _normalize_attachment(attachment: dict[str, Any], index: int) -> dict[str, Any]:
    filename = str(
        attachment.get("filename")
        or attachment.get("file_name")
        or attachment.get("name")
        or ""
    ).strip()
    if not filename:
        raise HTTPException(status_code=400, detail=f"第 {index} 个附件缺少文件名")

    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        allowed = ", ".join(sorted(_ALLOWED_SUFFIXES))
        raise HTTPException(status_code=400, detail=f"不支持的附件类型: {filename}。仅支持 {allowed}")

    raw_content = attachment.get("content")
    if raw_content is None:
        raw_content = attachment.get("data")
    if raw_content is None:
        raw_content = attachment.get("text")
    if raw_content is None:
        raise HTTPException(status_code=400, detail=f"附件 {filename} 缺少内容")

    return {
        **attachment,
        "filename": filename,
        "suffix": suffix,
        "content": raw_content,
        "content_encoding": str(
            attachment.get("content_encoding")
            or attachment.get("encoding")
            or "auto"
        ).lower(),
    }


def _parse_attachment(attachment: dict[str, Any]) -> str:
    filename = attachment["filename"]
    content = attachment["content"]
    content_encoding = attachment["content_encoding"]
    suffix = attachment["suffix"]

    try:
        file_bytes = _decode_attachment_bytes(content, content_encoding, suffix)
        parsed_text = parse_content_bytes(file_bytes, filename=filename)
    except UnicodeDecodeError as exc:
        if content_encoding == "auto" and suffix in _TEXT_SUFFIXES and isinstance(content, str):
            parsed_text = content
        else:
            raise HTTPException(status_code=400, detail=f"附件 {filename} 解析失败: {exc}") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"附件 {filename} 解析失败: {exc}") from exc

    parsed_text = parsed_text.strip()
    if not parsed_text:
        raise HTTPException(status_code=400, detail=f"附件 {filename} 未解析出有效文本")

    if len(parsed_text) > _MAX_PREVIEW_CHARS:
        parsed_text = parsed_text[:_MAX_PREVIEW_CHARS].rstrip() + "\n...[内容过长，已截断]"
    return parsed_text


def _decode_attachment_bytes(content: Any, content_encoding: str, suffix: str) -> bytes:
    if isinstance(content, bytes):
        return content
    if not isinstance(content, str):
        raise HTTPException(status_code=400, detail="附件内容必须为字符串或字节")

    if content.startswith("data:") and ";base64," in content:
        _, _, content = content.partition(",")
        content_encoding = "base64"

    if content_encoding == "auto":
        decoded = _try_decode_base64(content) if _looks_like_base64(content) else None
        if decoded is not None:
            return decoded
        if suffix in _TEXT_SUFFIXES:
            return content.encode("utf-8")
        raise HTTPException(status_code=400, detail="二进制附件默认需要使用 base64 编码传输")

    if content_encoding in {"text", "plain", "utf-8", "utf8"}:
        return content.encode("utf-8")
    if content_encoding in {"base64", "b64"}:
        decoded = _try_decode_base64(content)
        if decoded is None:
            raise HTTPException(status_code=400, detail="附件内容不是合法的 base64 编码")
        return decoded

    raise HTTPException(status_code=400, detail=f"不支持的附件编码方式: {content_encoding}")


def _try_decode_base64(content: str) -> bytes | None:
    try:
        return base64.b64decode(content, validate=True)
    except binascii.Error:
        return None


def _looks_like_base64(content: str) -> bool:
    stripped = content.strip()
    if not stripped or len(stripped) % 4 != 0:
        return False
    return bool(_BASE64_RE.fullmatch(stripped))


def _build_attachment_block(index: int, filename: str, parsed_text: str) -> str:
    return "\n".join([
        f"[附件 {index}] 文件名: {filename}",
        "以下为附件解析文本:",
        parsed_text,
    ])