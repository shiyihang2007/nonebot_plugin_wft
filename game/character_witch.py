"""Witch role: has one antidote (save) and one poison (kill)."""

from __future__ import annotations

from typing import Any

from .character_god import CharacterGod


class CharacterWitch(CharacterGod):
    """女巫：解药/毒药各一次（本实现中每晚最多执行一次动作）。"""

    role_id = "witch"
    name = "女巫"
    aliases = ["witch", "女巫", "巫", "药", "药师"]

    def __init__(self, room, player) -> None:
        super().__init__(room, player)
        self.has_antidote: bool = True
        self.has_poison: bool = True

    async def on_night_start(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        if not self.alive:
            return
        tips = [
            "天黑了，你是女巫。",
            "你可以：",
        ]
        if self.has_antidote:
            tips.append("- `/wft skill save` 使用解药（仅在狼刀确定后可救人）")
        if self.has_poison:
            tips.append("- `/wft skill poison <编号>` 使用毒药（例如：`/wft skill poison 3`）")
        tips.append("- `/wft skip` 放弃本夜行动")
        await self.send_private("\n".join(tips))

    async def on_use_skill(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        if not self.alive or user_id != self.user_id:
            return
        if self.room.state != "night":
            await self.send_private("现在不是夜晚阶段，无法使用女巫技能。")
            return
        if self.user_id in self.room.night_witch_done_user_ids:
            await self.send_private("你今晚已经完成用药/放弃，无需重复操作。")
            return
        if not args:
            await self.send_private("用法：`/wft skill save` 或 `/wft skill poison <编号>`")
            return

        op = args[0].lower()

        if op in {"save", "heal", "antidote", "jiu", "救", "解药", "救人"}:
            if not self.has_antidote:
                await self.send_private("你的解药已用完。")
                return
            ok, msg = await self.room.witch_save(self.user_id)
            if ok:
                self.has_antidote = False
                self.room.night_witch_done_user_ids.add(self.user_id)
            await self.send_private(msg)
            if ok:
                await self.room.try_advance()
            return

        if op in {"poison", "drug", "du", "毒", "毒药", "下毒"}:
            if not self.has_poison:
                await self.send_private("你的毒药已用完。")
                return
            if len(args) < 2 or not args[1].isdigit():
                await self.send_private("用法：`/wft skill poison <编号>`（编号需要是数字）")
                return
            seat = int(args[1])
            ok, msg = await self.room.witch_poison(self.user_id, seat)
            if ok:
                self.has_poison = False
                self.room.night_witch_done_user_ids.add(self.user_id)
            await self.send_private(msg)
            if ok:
                await self.room.try_advance()
            return
