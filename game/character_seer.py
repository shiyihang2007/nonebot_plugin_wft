"""预言家：每晚可查验一名玩家阵营（狼人/好人）。"""

from __future__ import annotations

import logging
from typing import Any

from .character_god import CharacterGod


class CharacterSeer(CharacterGod):
    """预言家：每晚可查验一名玩家阵营。"""

    aliases = ["seer", "预言家"]

    role_id = "seer"
    name = "预言家"

    def __init__(self, room, player) -> None:
        super().__init__(room, player)
        self._night_done: bool = False
        # 预言家专属事件：仅当场上存在预言家时才会创建/使用该事件
        room.events_system.get_or_create_event("seer_check").add_listener(
            self.on_seer_check_event, priority=0
        )

    async def on_night_start(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        logging.debug("监听器被触发: 名称 CharacterSeer.on_night_start")
        if not self.alive:
            return
        self._night_done = False
        # 等待“预言家动作”完成：为 night_end 增加一个锁
        self.room.events_system.event_night_end.lock()
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
        if self._night_done:
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
        ok, result = self._check(seat)
        if not ok:
            await self.send_private(result)
            return

        self._night_done = True
        await self.room.events_system.get_or_create_event("seer_check").active(
            self.room, self.user_id, [args[1], result]
        )
        await self.room.events_system.event_night_end.unlock(
            self.room, self.user_id, []
        )

    async def on_skip(self, room: Any, user_id: str | None, args: list[str]) -> None:
        if not self.alive or user_id != self.user_id:
            return
        if self.room.state != "night":
            return
        if self._night_done:
            return

        self._night_done = True
        await self.send_private("你已放弃本夜查验。")
        await self.room.events_system.event_night_end.unlock(
            self.room, self.user_id, []
        )

    async def on_seer_check_event(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        """事件 7：预言家查人。"""
        if not self.alive or user_id != self.user_id:
            return
        if not args:
            await self.send_private("用法：`/wft skill check <编号>`（编号需要是数字）")
            return

        if len(args) >= 2:
            await self.send_private(args[1])
            return

        if not args[0].isdigit():
            await self.send_private("用法：`/wft skill check <编号>`（编号需要是数字）")
            return

        seat = int(args[0])
        _, result = self._check(seat)
        await self.send_private(result)

    def _check(self, seat: int) -> tuple[bool, str]:
        """返回预言家对指定座位的查验结果文本（狼人/好人）。"""
        target = self.room.get_player_by_seat(seat)
        if not target:
            return False, "目标编号无效。"
        if not target.alive:
            return False, "目标已死亡。"
        if not target.role:
            return False, "目标身份未知。"
        result = "狼人" if target.role.camp == "wolf" else "好人"
        return True, f"查验结果: {target.seat}号 是 {result}。"
