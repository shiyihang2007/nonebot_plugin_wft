"""Minimal event dispatcher used by the room-based game loop."""

from __future__ import annotations

from typing import Any

from .listener import Listener


class EventBase:
    """A single event with an ordered list of async listeners."""

    def __init__(self) -> None:
        self.listeners: list[Listener] = []

    async def active(self, room: Any, user_id: str | None, args: list[str]) -> None:
        """Trigger the event and await each listener sequentially."""
        for listener in self.listeners:
            await listener(room, user_id, args)
