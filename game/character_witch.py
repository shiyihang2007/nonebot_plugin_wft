"""女巫：解药（救人）与毒药（杀人）各一次。"""

from __future__ import annotations

import logging
from typing import Any

from .event_base import EventBase
from .character_god import CharacterGod


class CharacterWitch(CharacterGod):
    """女巫：解药/毒药各一次"""

    role_id = "witch"
    name = "女巫"
    aliases = ["witch", "女巫", "巫", "药", "药师"]

    def __init__(self, room, player) -> None:
        super().__init__(room, player)
        self.has_antidote: bool = True
        self.has_poison: bool = True
        self._skill_available: bool = False
        self._wolf_kill_target_user_id: str | None = None

        self.event_wolf_lock: EventBase = room.events_system.get_or_create_event(
            "wolf_lock"
        )
        self.event_wolf_lock.add_listener(self.on_wolf_locked, priority=0)

    async def on_night_start(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        # 女巫在“狼刀锁定”后再行动
        self._skill_available = False
        self._wolf_kill_target_user_id = None
        return

    async def on_wolf_locked(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        """等待“女巫动作”：在狼刀锁定后提示女巫并锁定 night_end。"""
        logging.debug("监听器被触发: 名称 CharacterWitch.on_wolf_locked")
        if not self.alive:
            return
        if self.room.state != "night":
            return
        if not self.has_antidote and not self.has_poison:
            return
        if self._skill_available:
            return

        self._skill_available = True
        target_user_id = args[0].strip() if args else ""
        self._wolf_kill_target_user_id = target_user_id or None
        self.room.events_system.event_night_end.lock()

        tips: list[str] = []
        if self.has_antidote:
            if self._wolf_kill_target_user_id:
                victim = self.room.id_2_player.get(self._wolf_kill_target_user_id)
                if victim:
                    tips.append(f"当前狼刀落在：{victim.seat}号")
            else:
                tips.append("当前狼刀未指定/本夜可能平安")
        tips.append("你是女巫，你可以：")
        if self.has_antidote:
            tips.append("- `/wft skill save` 使用解药（仅在有狼刀目标时可救人）")
        if self.has_poison:
            tips.append(
                "- `/wft skill poison <编号>` 使用毒药（例如：`/wft skill poison 3`）"
            )
        tips.append("- `/wft skip` 放弃使用剩下的药")
        await self.send_private("\n".join(tips))

    async def on_use_skill(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        if not self.alive or user_id != self.user_id:
            return
        if self.room.state != "night":
            return
        if not self._skill_available:
            await self.send_private("你现在无法行动")
            return
        if not args:
            await self.send_private(
                "用法：`/wft skill save` 或 `/wft skill poison <编号>`"
            )
            return

        op = args[0].lower()
        if op in {"save", "heal", "antidote", "jiu", "救", "解药", "救人"}:
            if self.has_antidote:
                self.has_antidote = False
                if self._wolf_kill_target_user_id in self.room.pending_death_records:
                    del self.room.pending_death_records[self._wolf_kill_target_user_id]
                    victim = self.room.id_2_player.get(self._wolf_kill_target_user_id)
                    await self.send_private(
                        f"你使用了解药，救下了 {victim.seat if victim else -1}号。"
                    )
                    self.has_antidote = False
                else:
                    await self.send_private("没有人需要解救，解药未使用。")
            else:
                await self.send_private("你的解药已用完。")

        if op in {"poison", "drug", "du", "毒", "毒药", "下毒"}:
            if not self.has_poison:
                await self.send_private("你的毒药已用完。")
            elif len(args) < 2 or not args[1].isdigit():
                await self.send_private(
                    "用法：`/wft skill poison <编号>`（编号需要是数字）"
                )
            else:
                target = self.room.get_player_by_seat(int(args[1]))
                if not target:
                    await self.send_private("目标编号无效。")
                elif not target.alive:
                    await self.send_private("目标已死亡。")
                elif target.user_id == self.user_id:
                    await self.send_private("不能对自己使用毒药。")
                else:
                    self.has_poison = False
                    await self.send_private(f"你对 {target.seat}号 使用了毒药。")
                    self.room.pending_death_records[target.user_id] = "被毒死了"

        if not self.has_antidote and not self.has_poison:
            self._skill_available = False
            await self.send_private("你的药水已用完。")
            await self.room.events_system.event_night_end.unlock(
                self.room, self.user_id, []
            )

    async def on_skip(self, room: Any, user_id: str | None, args: list[str]) -> None:
        if not self.alive or user_id != self.user_id:
            return
        if self.room.state != "night":
            return
        if not self._skill_available:
            return

        self._skill_available = False
        await self.send_private("你已放弃本夜用药。")
        await self.room.events_system.event_night_end.unlock(
            self.room, self.user_id, []
        )
