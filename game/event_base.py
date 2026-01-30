from typing import Any
from listener import Listener


class EventBase:
    def __init__(self) -> None:
        self.listeners: list[Listener] = []

    async def active(self, room: Any, user_id: str | None, args: list[str]):
        for i in self.listeners:
            await i(room, user_id, args)
