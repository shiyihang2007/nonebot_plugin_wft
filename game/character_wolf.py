"""狼人：夜晚投票击杀目标（多数票可锁定击杀）。"""

from __future__ import annotations

from collections import Counter
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
        # 等待“狼人动作”完成：为 night_end 增加一个锁（每个存活狼人各占 1 票）
        self.room.events_system.event_night_end.lock()
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
        was_done = self.user_id in self.room.night_wolf_done_user_ids
        ok, msg = await self._vote_kill(seat)
        await self.send_private(msg)

        if not ok:
            return

        await self._after_wolf_response(was_done)

    async def on_skip(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        if not self.alive or user_id != self.user_id:
            return
        if self.room.state != "night":
            return
        if self.room.night_kill_locked:
            await self.send_private("狼人行动已锁定。")
            return

        was_done = self.user_id in self.room.night_wolf_done_user_ids
        if not was_done:
            self.room.night_wolf_done_user_ids.add(self.user_id)
            self._lock_kill_if_possible()
            await self.send_private("你已放弃本夜击杀投票。")

        await self._after_wolf_response(was_done)

    def _lock_kill_if_possible(self) -> None:
        """尝试锁定狼刀结果（多数票或全员回应）。"""
        if self.room.night_kill_locked:
            return
        wolves = self.room.alive_role_user_ids("wolf")
        if not wolves:
            self.room.night_kill_locked = True
            self.room.night_kill_target_user_id = None
            return

        votes = {uid: self.room.night_kill_votes.get(uid) for uid in wolves}
        votes = {uid: v for uid, v in votes.items() if v}

        if votes:
            counts = Counter(votes.values())
            top_target, top_count = counts.most_common(1)[0]
            if top_count > len(wolves) / 2:
                self.room.night_kill_locked = True
                self.room.night_kill_target_user_id = top_target
                return

        if wolves.issubset(self.room.night_wolf_done_user_ids):
            self.room.night_kill_locked = True
            self.room.night_kill_target_user_id = None

    async def _vote_kill(self, seat: int) -> tuple[bool, str]:
        """狼人击杀投票（仅修改房间的“夜晚结算”通用数据）。"""
        if self.room.state != "night":
            return False, "现在不是夜晚阶段。"
        if self.room.night_kill_locked:
            return False, "狼人行动已锁定。"
        if not self.alive:
            return False, "你不在游戏中，或已死亡。"

        target = self.room.get_player_by_seat(seat)
        if not target:
            return False, "目标编号无效。"
        if not target.alive:
            return False, "目标已死亡。"
        if target.user_id == self.user_id:
            return False, "不能选择自己作为击杀目标。"

        self.room.night_kill_votes[self.user_id] = target.user_id
        self.room.night_wolf_done_user_ids.add(self.user_id)
        self._lock_kill_if_possible()
        if self.room.night_kill_locked:
            if self.room.night_kill_target_user_id:
                victim = self.room.id_2_player[self.room.night_kill_target_user_id]
                return True, f"已投票击杀 {victim.seat}号。狼人行动已锁定。"
            return True, "已投票。狼人行动已锁定: 本夜无人死亡 (票型未达成多数) 。"
        return True, f"已投票击杀 {target.seat}号。"

    async def _after_wolf_response(self, was_done: bool) -> None:
        """狼人响应后推进流程：

        - 若狼刀已锁定：先触发 `wolf_locked`（让女巫等角色加锁），再释放所有狼人锁。
        - 否则：仅释放当前狼人自身的锁（等待其他狼人）。
        """
        # 如果狼刀已锁定且尚未触发 wolf_locked，先触发该事件（确保女巫先加锁）
        if self.room.night_kill_locked and not getattr(
            self.room, "_night_wolf_locked_event_fired", False
        ):
            self.room._night_wolf_locked_event_fired = True
            await self.room.events_system.event_wolf_locked.active(
                self.room, self.user_id, []
            )

            # 狼刀锁定后，其他狼人不再需要继续投票；释放所有未释放的狼人锁。
            for wolf_id in self.room.alive_role_user_ids("wolf"):
                if wolf_id not in self.room.night_wolf_done_user_ids:
                    self.room.night_wolf_done_user_ids.add(wolf_id)
                    await self.room.events_system.event_night_end.unlock(
                        self.room, wolf_id, []
                    )

            # 当前狼人首次回应也需要释放锁
            if not was_done:
                await self.room.events_system.event_night_end.unlock(
                    self.room, self.user_id, []
                )
            return

        # 未锁定：当前狼人首次回应后释放自身锁
        if not was_done:
            await self.room.events_system.event_night_end.unlock(
                self.room, self.user_id, []
            )
