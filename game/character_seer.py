"""Seer role: can check one player each night (wolf vs good)."""

from __future__ import annotations

from typing import Any

from .character_god import CharacterGod


class CharacterSeer(CharacterGod):
    """预言家：每晚可查验一名玩家阵营。"""

    aliases = ["seer", "预言家"]

    role_id = "seer"
    name = "预言家"

    async def on_night_start(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        if not self.alive:
            return
        await self.send_private(
            "天黑了，你是预言家。\n"
            "请使用 `/wft skill check <编号>` 查验身份（例如：`/wft skill check 3`），"
            "或使用 `/wft skip` 放弃本夜查验。"
        )

    async def on_use_skill(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        if not self.alive or user_id != self.user_id:
            return
        if self.room.state != "night":
            await self.send_private("现在不是夜晚阶段，无法查验。")
            return
        if self.user_id in self.room.night_seer_done_user_ids:
            await self.send_private("你今晚已经完成查验/放弃，无需重复操作。")
            return
        if not args:
            await self.send_private("用法：`/wft skill check <编号>`")
            return

        op = args[0].lower()
        if op not in {"check", "see", "inspect", "yan", "验", "查验", "查"}:
            return
        if len(args) < 2 or not args[1].isdigit():
            await self.send_private("用法：`/wft skill check <编号>`（编号需要是数字）")
            return

        seat = int(args[1])
        ok, result = self.room.seer_check(seat)
        if not ok:
            await self.send_private(result)
            return

        self.room.night_seer_done_user_ids.add(self.user_id)
        await self.send_private(result)
        await self.room.try_advance()
