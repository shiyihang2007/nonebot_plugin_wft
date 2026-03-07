"""黑狼王：既是狼人，也有猎枪"""

from __future__ import annotations

import logging
from typing import Any

from .character_wolf import CharacterWolf


class CharacterBlackWolf(CharacterWolf):
    """黑狼王：既是狼人，也有猎枪"""

    aliases = ["blackwolf", "黑狼王", "狼王", "黑狼"]

    role_id = "blackwolf"
    name = "黑狼王"

    def __init__(self, room, player) -> None:
        super().__init__(room, player)
        self.skill_shoot_available: bool = False
        self.blocked_event = None

        self.room.events_system.event_person_killed.add_listener(self.on_killed)
        self.room.events_system.event_skill.add_listener(self.on_skill)
        self.room.events_system.event_skip.add_listener(self.on_skip)

    async def on_killed(self, room: Any, user_id: str | None, args: list[str]) -> None:
        if user_id != self.user_id:
            return
        if args[0] == "被毒死了":
            await self.send_private("你被毒死了，无法使用猎枪")
            return

        self.skill_shoot_available = True

        self.blocked_event = self.room.events_system.get_event(args[1])
        if self.blocked_event:
            self.blocked_event.lock()

        tips: list[str] = []
        tips.append("你是黑狼王，你可以：")
        tips.append("- `/wft skill shoot <编号>` 枪杀一个人")
        tips.append("- `/wft skip` 放弃使用技能")
        await self.send_private("\n".join(tips))

    async def on_skill(self, room: Any, user_id: str | None, args: list[str]) -> None:
        if user_id != self.user_id:
            return
        if not self.skill_shoot_available:
            return
        if not args:
            await self.send_private("用法：`/wft skill shoot <编号>`")
            return
        op = args[0].lower()
        if op not in {"shoot", "枪", "qiang"}:
            return
        if len(args) < 2 or not args[1].isdigit():
            await self.send_private("用法：`/wft skill shoot <编号>`（编号需要是数字）")
            return

        target = self.room.get_player_by_seat(int(args[1]))
        if not target:
            await self.send_private("目标编号无效。")
        elif not target.alive:
            await self.send_private("目标已死亡。")
        else:
            await self.room.events_system.event_person_killed.active(
                self,
                target.user_id,
                ["被枪杀", self.blocked_event.name if self.blocked_event else ""],
            )
            self.skill_shoot_available = False

        if self.blocked_event:
            await self.blocked_event.unlock(self.room, self.user_id, [])

    async def on_skip(self, room: Any, user_id: str | None, args: list[str]) -> None:
        if not self.skill_shoot_available:
            return
        if user_id != self.user_id:
            return

        await self.send_private("你已放弃使用技能。")

        self.skill_shoot_available = False
        if self.blocked_event:
            await self.blocked_event.unlock(self.room, self.user_id, [])
