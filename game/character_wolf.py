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

    def __init__(self, room, player) -> None:
        super().__init__(room, player)
        self._night_responded: bool = False
        self._night_vote_target_user_id: str | None = None
        self._pack_locked: bool = False
        self._locked_target_user_id: str | None = None
        self._wolf_locked_event_fired: bool = False

    async def on_night_start(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        if not self.alive:
            return
        self._reset_pack_for_new_night()
        # 等待“狼人动作”完成：为 night_end 增加一个锁（每个存活狼人各占 1 票）
        self.room.events_system.event_night_end.lock()
        await self.send_private(
            "天黑了，你是狼人。\n"
            "请使用 `/wft skill kill <编号>` 选择击杀目标（例如：`/wft skill kill 3`），"
            "或使用 `/wft skip` 放弃本夜击杀投票。"
        )

    def get_night_kill_target_user_id(self) -> str | None:
        """返回狼人最终锁定的击杀目标 user_id；本夜无人死亡则为 None。"""
        if not self._pack_locked:
            return None
        return self._locked_target_user_id

    async def on_use_skill(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        if not self.alive or user_id != self.user_id:
            return
        if self.room.state != "night":
            await self.send_private("现在不是夜晚阶段，无法使用狼人的击杀。")
            return
        if self._pack_locked:
            await self.send_private("狼人行动已锁定。")
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
        was_done = self._night_responded
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
        if self._pack_locked:
            await self.send_private("狼人行动已锁定。")
            return

        was_done = self._night_responded
        if not was_done:
            self._night_responded = True
            self._try_lock_pack()
            await self.send_private("你已放弃本夜击杀投票。")

        await self._after_wolf_response(was_done)

    def _alive_wolves(self) -> list["CharacterWolf"]:
        wolves: list[CharacterWolf] = []
        for p in self.room.player_list:
            if not p.alive or not p.role:
                continue
            if getattr(p.role, "role_id", None) != "wolf":
                continue
            if isinstance(p.role, CharacterWolf):
                wolves.append(p.role)
        return wolves

    def _reset_pack_for_new_night(self) -> None:
        """重置狼人阵营本夜投票/锁定状态。"""
        for wolf in self._alive_wolves():
            wolf._night_responded = False
            wolf._night_vote_target_user_id = None
            wolf._pack_locked = False
            wolf._locked_target_user_id = None
            wolf._wolf_locked_event_fired = False

    def _set_pack_locked(self, target_user_id: str | None) -> None:
        for wolf in self._alive_wolves():
            wolf._pack_locked = True
            wolf._locked_target_user_id = target_user_id

    def _set_pack_wolf_locked_event_fired(self) -> None:
        for wolf in self._alive_wolves():
            wolf._wolf_locked_event_fired = True

    def _try_lock_pack(self) -> None:
        """尝试锁定狼刀结果（多数票或全员回应）。"""
        if self._pack_locked:
            return
        wolves = self._alive_wolves()
        if not wolves:
            self._set_pack_locked(None)
            return

        votes = [w._night_vote_target_user_id for w in wolves if w._night_vote_target_user_id]
        if votes:
            counts = Counter(votes)
            top_target, top_count = counts.most_common(1)[0]
            if top_count > len(wolves) / 2:
                self._set_pack_locked(top_target)
                return

        if all(w._night_responded for w in wolves):
            self._set_pack_locked(None)

    async def _vote_kill(self, seat: int) -> tuple[bool, str]:
        """狼人击杀投票（仅修改房间的“夜晚结算”通用数据）。"""
        if self.room.state != "night":
            return False, "现在不是夜晚阶段。"
        if self._pack_locked:
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

        self._night_vote_target_user_id = target.user_id
        self._night_responded = True
        self._try_lock_pack()
        if self._pack_locked:
            if self._locked_target_user_id:
                victim = self.room.id_2_player[self._locked_target_user_id]
                return True, f"已投票击杀 {victim.seat}号。狼人行动已锁定。"
            return True, "已投票。狼人行动已锁定: 本夜无人死亡 (票型未达成多数) 。"
        return True, f"已投票击杀 {target.seat}号。"

    async def _after_wolf_response(self, was_done: bool) -> None:
        """狼人响应后推进流程：

        - 若狼刀已锁定：先触发 `wolf_locked`（让女巫等角色加锁），再释放所有狼人锁。
        - 否则：仅释放当前狼人自身的锁（等待其他狼人）。
        """
        # 若本次行动让狼刀达成锁定，记录 pack 状态（投票/跳过可能导致“全员回应”锁定）
        self._try_lock_pack()

        # 如果狼刀已锁定且尚未触发 wolf_locked，先触发该事件（确保女巫先加锁）
        if self._pack_locked and not any(
            w._wolf_locked_event_fired for w in self._alive_wolves()
        ):
            self._set_pack_wolf_locked_event_fired()
            target_user_id = self._locked_target_user_id or ""
            await self.room.events_system.event_wolf_locked.active(
                self.room, self.user_id, [target_user_id]
            )

            # 狼刀锁定后，其他狼人不再需要继续投票；释放所有未释放的狼人锁。
            for wolf in self._alive_wolves():
                if not wolf._night_responded:
                    wolf._night_responded = True
                    await self.room.events_system.event_night_end.unlock(
                        self.room, wolf.user_id, []
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
