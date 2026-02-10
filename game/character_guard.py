"""守卫：夜晚守护一名玩家（不可连续两晚守同一目标）。"""

from __future__ import annotations

from typing import Any

from .character_god import CharacterGod


class CharacterGuard(CharacterGod):
    """守卫：夜晚守护一名玩家，被守护者不会被狼刀杀死。"""

    role_id = "guard"
    name = "守卫"
    aliases = ["guard", "守卫", "守"]

    def __init__(self, room, player) -> None:
        super().__init__(room, player)
        self._night_done: bool = False
        self._night_target_user_id: str | None = None
        self._last_target_user_id: str | None = None

    async def on_night_start(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        if not self.alive:
            return
        self._night_done = False
        self._night_target_user_id = None
        # 等待“守卫动作”完成：为 night_end 增加一个锁
        self.room.events_system.event_night_end.lock()
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
        if self._night_done:
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
        ok, msg = await self._protect(seat)
        await self.send_private(msg)
        if not ok:
            return

        await self.room.events_system.event_night_end.unlock(
            self.room, self.user_id, []
        )

    async def on_skip(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        if not self.alive or user_id != self.user_id:
            return
        if self.room.state != "night":
            return
        if self._night_done:
            return

        self._night_done = True
        await self.send_private("你已放弃本夜守护。")
        await self.room.events_system.event_night_end.unlock(
            self.room, self.user_id, []
        )

    def get_night_protect_target_user_id(self) -> str | None:
        """返回本夜守护目标的 user_id；未守护则为 None。"""
        return self._night_target_user_id

    async def _protect(self, seat: int) -> tuple[bool, str]:
        """守卫守护目标（仅修改房间的“夜晚结算”通用数据）。"""
        if self.room.state != "night":
            return False, "现在不是夜晚阶段。"
        if not self.alive:
            return False, "你不在游戏中，或已死亡。"

        target = self.room.get_player_by_seat(seat)
        if not target:
            return False, "目标编号无效。"
        if not target.alive:
            return False, "目标已死亡。"

        last = self._last_target_user_id
        if last and last == target.user_id:
            return False, "不能连续两晚守护同一名玩家。"

        self._night_target_user_id = target.user_id
        self._night_done = True
        self._last_target_user_id = target.user_id
        return True, f"你将守护 {target.seat}号。"
