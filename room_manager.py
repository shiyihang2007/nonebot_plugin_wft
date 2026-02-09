"""RoomManager: maintain per-group rooms and serialize operations.

NoneBot handlers are concurrent; without serialization, multiple commands from the same
group can interleave and corrupt room state. This manager provides:

- a `rooms` mapping (group_id -> Room)
- a per-group `asyncio.Lock` to ensure operations are executed sequentially
"""

from __future__ import annotations

import asyncio

from .game.room import Room


class RoomManager:
    """Manage rooms and provide per-room locks."""

    def __init__(self) -> None:
        self.rooms: dict[str, Room] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def lock(self, group_id: str) -> asyncio.Lock:
        """Return the per-group lock (created lazily)."""
        group_id = str(group_id)
        if group_id not in self._locks:
            self._locks[group_id] = asyncio.Lock()
        return self._locks[group_id]

