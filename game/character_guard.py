"""守卫：夜晚守护一名玩家（不可连续两晚守同一目标）。"""

from __future__ import annotations

import logging
from typing import Any

from .character_god import CharacterGod


class CharacterGuard(CharacterGod):
    """守卫：夜晚守护一名玩家，被守护者不会被狼刀杀死。"""

    role_id = "guard"
    name = "守卫"
    aliases = ["guard", "守卫", "守"]

    def __init__(self, room, player) -> None:
        super().__init__(room, player)
        self._guard_user_id: str | None = None
        self._last_guard_user_id: str | None = None
        self._night_responded: bool = False

        self.room.events_system.event_night_end.add_listener(self.on_night_end)

    async def on_night_start(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        logging.debug("监听器被触发: 名称 CharacterGuard.on_night_start")
        if not self.alive:
            return
        self._guard_user_id = None
        self.room.events_system.event_night_end.lock()
        self._night_responded = False
        await self.send_private(
            "你是守卫，你可以：\n"
            "- 使用 `/wft skill guard <编号>` 守护一名玩家（例如：`/wft skill guard 3`）；"
            "- 使用 `/wft skip` 放弃本夜守护；"
            "在天亮前你都有机会改变你的选择。"
        )

    async def on_use_skill(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        if not self.alive or user_id != self.user_id:
            return
        if self.room.state != "night":
            return
        if not args:
            await self.send_private("用法：`/wft skill guard <编号>`")
            return

        op = args[0].lower()
        if op not in {"guard", "protect", "shou", "守", "守护"}:
            return
        if len(args) < 2 or not args[1].isdigit():
            await self.send_private("用法：`/wft skill guard <编号>`（编号需要是数字）")
            return

        seat = int(args[1])
        target = self.room.get_player_by_seat(seat)
        if not target:
            await self.send_private("目标编号无效。")
            return
        if not target.alive:
            await self.send_private("目标已死亡。")
            return

        last = self._last_guard_user_id
        if last and last == target.user_id:
            await self.send_private("不能连续两晚守护同一名玩家。")
            return

        await self.send_private(
            f"你将{'改为' if self._guard_user_id else ''}守护 {target.seat}号。"
        )
        self._guard_user_id = target.user_id
        if not self._night_responded:
            await self.room.events_system.event_night_end.unlock(
                self.room, self.user_id, []
            )
            self._night_responded = True

    async def on_skip(self, room: Any, user_id: str | None, args: list[str]) -> None:
        if not self.alive or user_id != self.user_id:
            return
        if self.room.state != "night":
            return

        await self.send_private("你已放弃本夜守护。")
        self._guard_user_id = None
        if not self._night_responded:
            await self.room.events_system.event_night_end.unlock(
                self.room, self.user_id, []
            )
            self._night_responded = True

    async def on_night_end(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        "注入夜晚结束的处理，将被守护目标从将死列表中除去（如果目标被刀的话）"
        self._last_guard_user_id = self._guard_user_id
        if self._guard_user_id not in self.room.pending_death_records:
            return
        if self.room.pending_death_records[self._guard_user_id] != "被狼刀了":
            return
        del self.room.pending_death_records[self._guard_user_id]
