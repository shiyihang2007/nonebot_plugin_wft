"""女巫：解药（救人）与毒药（杀人）各一次。"""

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
        room.events_system.event_wolf_locked.add_listener(
            self.on_wolf_locked, priority=0
        )

    async def on_night_start(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        # 女巫在“狼刀锁定”后再行动（见 docs/wft_event_graph.md：4 -> 5）。
        return

    async def on_wolf_locked(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        """等待“女巫动作”：在狼刀锁定后提示女巫并锁定 night_end。"""
        if not self.alive:
            return
        if self.room.state != "night":
            return
        if self.user_id in self.room.night_witch_done_user_ids:
            return

        self.room.events_system.event_night_end.lock()

        tips: list[str] = ["狼人行动已锁定，你是女巫。", "你可以："]
        if self.room.night_kill_target_user_id:
            victim = self.room.id_2_player.get(self.room.night_kill_target_user_id)
            if victim:
                tips.append(f"- 当前狼刀落在：{victim.seat}号")
        else:
            tips.append("- 当前狼刀未指定/本夜可能平安")

        if self.has_antidote:
            tips.append("- `/wft skill save` 使用解药（仅在有狼刀目标时可救人）")
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
        if not self.room.night_kill_locked:
            await self.send_private("请等待狼人行动锁定后再行动。")
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
            ok, msg = await self._save()
            if ok:
                self.has_antidote = False
            await self.send_private(msg)
            if ok:
                await self.room.events_system.event_night_end.unlock(
                    self.room, self.user_id, []
                )
            return

        if op in {"poison", "drug", "du", "毒", "毒药", "下毒"}:
            if not self.has_poison:
                await self.send_private("你的毒药已用完。")
                return
            if len(args) < 2 or not args[1].isdigit():
                await self.send_private("用法：`/wft skill poison <编号>`（编号需要是数字）")
                return
            seat = int(args[1])
            ok, msg = await self._poison(seat)
            if ok:
                self.has_poison = False
            await self.send_private(msg)
            if ok:
                await self.room.events_system.event_night_end.unlock(
                    self.room, self.user_id, []
                )
            return

    async def on_skip(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        if not self.alive or user_id != self.user_id:
            return
        if self.room.state != "night":
            return
        if not self.room.night_kill_locked:
            return
        if self.user_id in self.room.night_witch_done_user_ids:
            return

        self.room.night_witch_done_user_ids.add(self.user_id)
        await self.send_private("你已放弃本夜用药。")
        await self.room.events_system.event_night_end.unlock(self.room, self.user_id, [])

    async def _save(self) -> tuple[bool, str]:
        """使用解药取消本夜狼刀（仅修改房间的“夜晚结算”通用数据）。"""
        if self.room.state != "night":
            return False, "现在不是夜晚阶段。"
        if self.room.night_witch_saved:
            return False, "本夜已使用过解药。"
        if not self.room.night_kill_target_user_id:
            return False, "当前没有可救的人 (狼刀未确定或本夜平安) 。"

        self.room.night_witch_saved = True
        self.room.night_witch_done_user_ids.add(self.user_id)
        victim = self.room.id_2_player.get(self.room.night_kill_target_user_id)
        if victim:
            return True, f"你使用了解药，救下了 {victim.seat}号。"
        return True, "你使用了解药。"

    async def _poison(self, seat: int) -> tuple[bool, str]:
        """对玩家下毒（仅修改房间的“夜晚结算”通用数据）。"""
        if self.room.state != "night":
            return False, "现在不是夜晚阶段。"

        target = self.room.get_player_by_seat(seat)
        if not target:
            return False, "目标编号无效。"
        if not target.alive:
            return False, "目标已死亡。"
        if target.user_id == self.user_id:
            return False, "不能对自己使用毒药。"
        if self.user_id in self.room.night_witch_poison_target_by_user_id:
            return False, "你本夜已经使用过毒药。"

        self.room.night_witch_poison_target_by_user_id[self.user_id] = target.user_id
        self.room.night_witch_done_user_ids.add(self.user_id)
        return True, f"你对 {target.seat}号 使用了毒药。"
