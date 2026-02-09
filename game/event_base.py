"""房间制游戏循环使用的最小事件分发器。"""

from __future__ import annotations

from typing import Any

from .listener import Listener


class EventBase:
    """单个事件，包含按顺序执行的异步监听器列表。"""

    def __init__(self) -> None:
        self.listeners: list[Listener] = []

    async def active(self, room: Any, user_id: str | None, args: list[str]) -> None:
        """触发事件并按顺序 await 每个监听器。"""
        for listener in self.listeners:
            await listener(room, user_id, args)
