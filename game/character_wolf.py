"""狼人：夜晚投票击杀目标。"""

from __future__ import annotations

from collections import Counter
from typing import Any, TYPE_CHECKING

from .event_base import EventBase
from .character_base import CharacterBase

if TYPE_CHECKING:
    from .room import Room


class CharacterWolf(CharacterBase):
    """狼人：夜晚投票击杀目标。"""

    role_id = "wolf"
    name = "狼人"
    camp = "wolf"
    aliases = ["wolf", "狼"]

    def __init__(self, room: Room, player) -> None:
        super().__init__(room, player)
        self.kill_responded: bool = False
        self.night_vote_target_user_id: str | None = None
        self.skill_kill_available: bool = True
        self.locked_target_user_id: str | None = None
        self.event_wolf_locked: EventBase = room.events_system.get_or_create_event(
            "wolf_lock"
        )
        self.event_wolf_locked.add_listener(self.on_wolf_locked)

    def _reset_pack_for_new_night(self) -> None:
        """重置狼人阵营本夜投票/锁定状态。"""
        for wolf in self._alive_wolves():
            wolf.kill_responded = False
            wolf.night_vote_target_user_id = None
            wolf.skill_kill_available = True
            wolf.locked_target_user_id = None

    async def on_night_start(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        if not self.alive:
            return
        self._reset_pack_for_new_night()
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
        if not self.skill_kill_available:
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
        target = self.room.get_player_by_seat(seat)
        if not target:
            await self.send_private("目标编号无效。")
            return
        if not target.alive:
            await self.send_private("目标已死亡。")
            return
        if target.user_id == self.user_id:
            await self.send_private("不能选择自己作为击杀目标。")
            return

        self.night_vote_target_user_id = target.user_id
        if not self.kill_responded:
            self.kill_responded = True

        await self.send_private(f"已投票击杀 {target.seat}号。")
        await self._try_lock_pack()

    async def on_skip(self, room: Any, user_id: str | None, args: list[str]) -> None:
        if not self.alive or user_id != self.user_id:
            return
        if not self.skill_kill_available:
            return

        self.kill_responded = True
        self.night_vote_target_user_id = None
        await self.send_private("你已放弃本夜击杀投票。")
        await self._try_lock_pack()

    async def on_wolf_locked(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        """狼刀锁定"""
        self.skill_kill_available = False

    def _alive_wolves(self) -> list[CharacterWolf]:
        wolves: list[CharacterWolf] = []
        for p in self.room.player_list:
            if not p.alive or not p.role:
                continue
            if getattr(p.role, "role_id", None) != "wolf":
                continue
            if isinstance(p.role, CharacterWolf):
                wolves.append(p.role)
        return wolves

    async def _try_lock_pack(self) -> None:
        """尝试锁定狼刀结果（多数票或全员回应）。"""
        wolves = self._alive_wolves()
        votes = [
            w.night_vote_target_user_id for w in wolves if w.night_vote_target_user_id
        ]
        if votes:
            counts = Counter(votes)
            top_target, top_count = counts.most_common(1)[0]
            if top_count > len(wolves) / 2:
                await self.event_wolf_locked.active(self.room, self.name, [top_target])
                self.room.pending_death_records[top_target] = "被狼刀了"
                return
        if all(w.kill_responded for w in wolves):
            await self.event_wolf_locked.active(self.room, self.name, [""])
