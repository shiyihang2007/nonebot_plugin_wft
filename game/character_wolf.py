"""Wolf role: votes to kill a target at night (majority locks the kill)."""

from __future__ import annotations

from typing import Any

from .character_base import CharacterBase


class CharacterWolf(CharacterBase):
    """狼人：夜晚投票击杀目标。"""

    role_id = "wolf"
    name = "狼人"
    camp = "wolf"
    aliases = ["wolf", "狼"]

    async def on_night_start(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        if not self.alive:
            return
        await self.send_private(
            "天黑了，你是狼人。\n"
            "请使用 `/wft skill kill <编号>` 选择击杀目标（例如：`/wft skill kill 3`），"
            "或使用 `/wft skip` 放弃本夜击杀投票。"
        )

    async def on_use_skill(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        if not self.alive or user_id != self.user_id:
            return
        if self.room.state != "night":
            await self.send_private("现在不是夜晚阶段，无法使用狼人的击杀。")
            return
        if not args:
            await self.send_private("用法：`/wft skill kill <编号>`")
            return

        op = args[0].lower()
        if op not in {"kill", "knife", "sha", "杀", "刀"}:
            return
        if len(args) < 2 or not args[1].isdigit():
            await self.send_private("用法：`/wft skill kill <编号>`（编号需要是数字）")
            return

        seat = int(args[1])
        ok, msg = await self.room.wolf_vote_kill(self.user_id, seat)
        await self.send_private(msg)
        if ok:
            await self.room.try_advance()
