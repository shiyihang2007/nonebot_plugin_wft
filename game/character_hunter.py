"""猎人：被狼人杀害或投票放逐时可以指定枪杀一名玩家。"""

from __future__ import annotations

import logging
from typing import Any

from .character_god import CharacterGod


class CharacterHunter(CharacterGod):
    """预言家：猎人：被狼人杀害或投票放逐时可以指定枪杀一名玩家。"""

    aliases = ["hunter", "猎人"]

    role_id = "hunter"
    name = "猎人"

    def __init__(self, room, player) -> None:
        super().__init__(room, player)
        self.have_skill : bool = False
        self.skill_time : str | None = None

        self.room.events_system.event_person_killed.add_listener(self.on_killed)
        self.room.events_system.event_skill.add_listener(self.on_skill)
        self.room.events_system.event_skip.add_listener(self.on_skip)

    async def on_killed(self, room: Any, user_id: str | None, args: list[str]) -> None:
        if user_id != self.user_id:
            return
        if args[0] == "被毒死了":
            return

        self.have_skill = True
        self.room.events_system.event_skill.add_listener(self.on_skill)
        self.room.events_system.event_skip.add_listener(self.on_skip)

        if args[1] == "day_start":
            self.skill_time = "vote_start"
            self.room.events_system.event_vote_start.lock()
        else:
            self.skill_time = "day_end"
            self.room.events_system.event_day_end.lock()

        tips: list[str] = []
        tips.append("你是猎人，你可以：")
        tips.append("- `/wft skill shoot <编号>` 枪杀一个人")
        tips.append("- `/wft skip` 放弃使用技能")
        await self.send_private("\n".join(tips))

    async def on_skill(self, room: Any, user_id: str | None, args: list[str]) -> None:
        if user_id != self.user_id:
            return
        if not args:
            await self.send_private("用法：`/wft skill shoot <编号>`")
            return

        op = args[0].lower()
        if op not in {"shoot", "kill"}:
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
            self.room.pending_death_records[target.user_id] = "被猎人枪杀"
            self.have_skill = False

        if self.skill_time == "vote_start":
            await self.room.events_system.event_vote_start.unlock(
                self.room, self.user_id, []
            )
        else:
            await self.room.events_system.event_day_end.unlock(
                self.room, self.user_id, []
            )

    async def on_skip(self, room: Any, user_id: str | None, args: list[str]) -> None:
        if user_id != self.user_id:
            return
        if not args:
            await self.send_private("用法：`/wft skill shoot <编号>`")
            return

        await self.send_private("你已放弃使用技能。")

        if self.skill_time == "vote_start":
            await self.room.events_system.event_vote_start.unlock(
                self.room, self.user_id, []
            )
        else:
            await self.room.events_system.event_day_end.unlock(
                self.room, self.user_id, []
            )
