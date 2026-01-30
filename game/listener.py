"""Typing-only protocol for async event listeners."""

from __future__ import annotations

from typing import Any, Protocol


class Listener(Protocol):
    async def __call__(self, room: Any, user_id: str | None, args: list[str]) -> Any: ...
