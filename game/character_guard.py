"""Guard role: protects one player at night (cannot protect same target consecutively)."""

from __future__ import annotations

from typing import Any

from .character_god import CharacterGod


class CharacterGuard(CharacterGod):
    """守卫：夜晚守护一名玩家，被守护者不会被狼刀杀死。"""

    role_id = "guard"
    name = "守卫"
    aliases = ["guard", "守卫", "守"]

    async def on_night_start(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        if not self.alive:
            return
        await self.send_private(
            "天黑了，你是守卫。\n"
            "请使用 `/wft skill guard <编号>` 守护一名玩家（例如：`/wft skill guard 3`），"
            "或使用 `/wft skip` 放弃本夜守护。"
        )

    async def on_use_skill(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        if not self.alive or user_id != self.user_id:
            return
        if self.room.state != "night":
            await self.send_private("现在不是夜晚阶段，无法守护。")
            return
        if self.user_id in self.room.night_guard_done_user_ids:
            await self.send_private("你今晚已经完成守护/放弃，无需重复操作。")
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
        ok, msg = await self.room.guard_protect(self.user_id, seat)
        await self.send_private(msg)
        if ok:
            await self.room.try_advance()
