"""RoomManager：维护按群的房间并串行化操作。

NoneBot handler 默认并发执行；若不做串行化，同一群的多条指令可能交错执行并破坏房间状态。
本管理器提供：

- `rooms` 映射（group_id -> Room）
- 每群一个 `asyncio.Lock`，确保对同一房间的操作按顺序执行
"""

from __future__ import annotations

import asyncio

from .game.room import Room


class RoomManager:
    """管理房间并提供每群锁。"""

    def __init__(self) -> None:
        self.rooms: dict[str, Room] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def lock(self, group_id: str) -> asyncio.Lock:
        """获取群级锁（按需创建）。"""
        group_id = str(group_id)
        if group_id not in self._locks:
            self._locks[group_id] = asyncio.Lock()
        return self._locks[group_id]
