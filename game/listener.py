"""异步事件监听器的类型协议（仅用于类型标注）。"""

from __future__ import annotations

from typing import Any, Protocol


class Listener(Protocol):
    async def __call__(self, room: Any, user_id: str | None, args: list[str]) -> Any: ...
