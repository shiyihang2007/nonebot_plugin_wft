"""单个 `Room` 实例的事件容器。"""

from __future__ import annotations

from .event_base import EventBase


class EventSystem:
    """角色监听器使用的一组事件通道。"""

    def __init__(self) -> None:
        self.event_night_start = EventBase()
        self.event_day_start = EventBase()
        self.event_vote_start = EventBase()

        self.event_use_skill = EventBase()
        self.event_person_killed = EventBase()
