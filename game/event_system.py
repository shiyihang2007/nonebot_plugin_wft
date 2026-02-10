"""单个 `Room` 实例的事件容器。

约定：
- 事件系统仅用于“对局内事件”（流程推进、玩家操作、角色技能等）。
- 房间/大厅管理（init/join/exit/addrole/...）不应通过事件系统处理。
"""

from __future__ import annotations

from .event_base import EventBase


class EventSystem:
    """角色监听器使用的一组事件通道。

除固定事件外，也支持在运行时按名称创建事件（用于角色扩展点）。
"""

    def __init__(self) -> None:
        self.events: dict[str, EventBase] = {}

        # === 核心流程事件（对照 docs/wft_event_graph.md） ===
        self.event_game_start = self._new_event("game_start")  # 1
        self.event_night_start = EventBase()
        self.event_day_start = EventBase()
        self.event_vote_start = EventBase()

        self.event_wolf_locked = self._new_event("wolf_locked")  # 4
        self.event_night_end = self._new_event("night_end")  # 10
        self.event_vote_end = self._new_event("vote_end")  # 24
        self.event_day_end = self._new_event("day_end")  # 30
        self.event_game_end = self._new_event("game_end")  # 100

        # === 玩家操作事件 ===
        self.event_use_skill = EventBase()
        self.event_vote = self._new_event("vote")  # 玩家投票输入
        self.event_skip = self._new_event("skip")  # 玩家跳过/结束发言/弃票/放弃技能

        # === 通用事件 ===
        self.event_person_killed = EventBase()

        # 兼容：保留旧字段名的创建方式（逐步迁移到 _new_event）
        self.events.setdefault("night_start", self.event_night_start)
        self.events.setdefault("day_start", self.event_day_start)
        self.events.setdefault("vote_start", self.event_vote_start)
        self.events.setdefault("use_skill", self.event_use_skill)
        self.events.setdefault("person_killed", self.event_person_killed)

    def _new_event(self, name: str) -> EventBase:
        event = EventBase()
        self.events[name] = event
        return event

    def get_event(self, name: str) -> EventBase | None:
        """按名称获取事件；不存在则返回 None。"""
        return self.events.get(name)

    def get_or_create_event(self, name: str) -> EventBase:
        """按名称获取事件；不存在则创建。"""
        event = self.events.get(name)
        if event is None:
            event = self._new_event(name)
        return event
