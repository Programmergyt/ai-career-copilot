"""会话内短期记忆 — 基于 LangGraph State 的会话状态管理"""


class SessionMemory:
    """会话内存管理，保存单次运行的中间结果。"""

    def __init__(self):
        self._store: dict = {}

    def set(self, key: str, value) -> None:
        self._store[key] = value

    def get(self, key: str, default=None):
        return self._store.get(key, default)

    def clear(self) -> None:
        self._store.clear()

    def to_dict(self) -> dict:
        return dict(self._store)
