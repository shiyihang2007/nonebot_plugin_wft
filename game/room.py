"""nonebot_plugin_wft 的房间对象与对局流程控制（事件驱动）。

本版本不再通过“显式状态机函数链（start_xxx/resolve_xxx/try_advance）”推进流程，
而是由 `EventSystem` + `EventBase.lock/unlock` 控制对局事件的触发顺序与等待点。

对照 `docs/wft_event_graph.md` 的关键事件（简化命名）：

- `game_start`：游戏开始
- `night_start`：夜晚开始
- `wolf_locked`：狼人刀口锁定
- `night_end`：夜晚结束（结算夜晚）
- `person_killed`：玩家死亡（可携带“下一事件”参数）
- `day_start`：白天开始
- `vote_start` / `vote_end`：投票开始/结束
- `day_end`：白天结束
- `game_end`：终局

玩家输入也事件化：
- `use_skill`：`wft.skill ...`
- `skip`：`wft.skip`
- `vote`：`wft.vote ...`
"""

from __future__ import annotations

import logging
import random
from collections import Counter

from .utils import get_classes_in_module, get_modules_in_package_by_prefix
from .player import Player

from .character_base import CharacterBase
from .character_person import CharacterPerson
from .event_system import EventSystem


_logger = logging.getLogger(__name__)


def _load_character_classes() -> list[type[CharacterBase]]:
    """通过导入本包下的 `character_*.py` 模块加载所有角色类。"""
    character_modules = get_modules_in_package_by_prefix(__package__, "character_")
    classes: list[type[CharacterBase]] = []
    for module in character_modules:
        for cls in get_classes_in_module(module):
            if getattr(cls, "__module__", None) != getattr(module, "__name__", None):
                continue
            try:
                if issubclass(cls, CharacterBase) and cls is not CharacterBase:
                    classes.append(cls)
            except TypeError:
                # cls is not a class
                continue
    return classes


def _build_character_registry(
    classes: list[type[CharacterBase]],
) -> tuple[
    list[type[CharacterBase]],
    dict[str, type[CharacterBase]],
    dict[str, type[CharacterBase]],
]:
    """从扫描到的角色类构建 `role_id` / `aliases` 查找表。

    - 强制 `role_id` 唯一（后出现的重复项会记录日志并忽略）。
    - 强制 alias 唯一（后出现的冲突项会记录日志并忽略）。
    """
    role_id_2_cls: dict[str, type[CharacterBase]] = {}
    alias_2_cls: dict[str, type[CharacterBase]] = {}

    for cls in classes:
        role_id = getattr(cls, "role_id", None)
        if not isinstance(role_id, str) or not role_id:
            _logger.warning("Ignore role class without role_id: %s", cls)
            continue

        if role_id in role_id_2_cls and role_id_2_cls[role_id] is not cls:
            _logger.error(
                "Duplicate role_id %r: %s vs %s (ignored: %s)",
                role_id,
                role_id_2_cls[role_id],
                cls,
                cls,
            )
            continue

        role_id_2_cls[role_id] = cls

        aliases = getattr(cls, "aliases", None)
        if not isinstance(aliases, list):
            continue
        for alias in aliases:
            if not isinstance(alias, str) or not alias:
                continue
            if alias in alias_2_cls and alias_2_cls[alias] is not cls:
                _logger.error(
                    "Alias conflict %r: %s vs %s (ignored: %s)",
                    alias,
                    alias_2_cls[alias],
                    cls,
                    cls,
                )
                continue
            alias_2_cls[alias] = cls

    unique_classes = list(role_id_2_cls.values())
    return unique_classes, role_id_2_cls, alias_2_cls


character_classes, role_id_2_character_cls, alias_2_character_cls = (
    _build_character_registry(_load_character_classes())
)


def get_character_class_by_role_id(role_id: str) -> type[CharacterBase] | None:
    """按 `role_id` 查找角色类（例如：`wolf`）。"""
    return role_id_2_character_cls.get(role_id)


def get_character_class_by_alias(alias: str) -> type[CharacterBase] | None:
    """按别名文本查找角色类（例如：`狼`、`seer`）。"""
    return alias_2_character_cls.get(alias)


class Room:
    """按群划分的游戏房间（同一 `group_id` 同时仅允许一局）。

    说明：
    - 房间/大厅管理：直接方法（join/exit/addrole/...），不走事件系统
    - 对局流程推进：使用 `events_system` 的事件链 + `lock/unlock`
    """

    def __init__(
        self, group_id: str, func_send_group_message, func_send_private_message
    ) -> None:
        # NoneBot/OneBot APIs expect numeric ids, but we store them as str internally.
        self.group_id: str = str(group_id)
        self.func_send_group_message = func_send_group_message
        self.func_send_private_message = func_send_private_message
        self.player_list: list[Player] = []
        self.id_2_player: dict[str, Player] = {}
        self.events_system: EventSystem = EventSystem()
        self.character_enabled: dict[type[CharacterBase], int] = {}
        self.settings: dict[str, int | str | bool] = {}

        # 对局阶段（用于校验玩家输入；推进由事件系统的 lock/unlock 触发）
        # - lobby：未开始，可加入/配置
        # - night：夜晚（私聊技能/跳过）
        # - speech：白天轮流发言（群聊 skip 推进）
        # - vote：白天投票（群聊 vote/skip）
        # - ended：终局
        self.state: str = "lobby"

        self.day_count: int = 0
        self.day_speech_order_user_ids: list[str] = []
        self.day_speech_index: int = 0

        self.night_kill_votes: dict[str, str] = {}
        self.night_wolf_done_user_ids: set[str] = set()
        self.night_kill_target_user_id: str | None = None
        self.night_kill_locked: bool = False
        self._night_wolf_locked_event_fired: bool = False
        self.night_seer_done_user_ids: set[str] = set()

        self.night_guard_target_by_user_id: dict[str, str] = {}
        self.guard_last_target_by_user_id: dict[str, str] = {}
        self.night_guard_done_user_ids: set[str] = set()

        self.night_witch_done_user_ids: set[str] = set()
        self.night_witch_saved: bool = False
        self.night_witch_poison_target_by_user_id: dict[str, str] = {}

        self.votes: dict[str, str | None] = {}
        self.last_night_death_user_ids: list[str] = []

        # 事件驱动流程的运行时状态（尽量保持“可扩展”且不耦合具体角色实现）。
        self._pending_death_records: list[tuple[str, str]] = []  # (user_id, reason)
        self.vote_pending_user_ids: set[str] = set()

    async def broadcast(self, message: str) -> None:
        """向房间所在群发送消息。"""
        await self.func_send_group_message(group_id=int(self.group_id), message=message)

    async def post_to_player(self, user_id: str, message: str) -> None:
        """给玩家发送私聊消息。"""
        await self.func_send_private_message(user_id=int(user_id), message=message)

    async def add_player(self, user_id: str) -> None:
        """将玩家加入房间（座位顺序按加入顺序）。"""
        if user_id in self.id_2_player:
            await self.broadcast(f"玩家 {user_id} 已在房间内")
            return
        self.id_2_player[user_id] = Player(user_id, len(self.player_list))
        self.player_list.append(self.id_2_player[user_id])

    async def remove_player(self, user_id: str) -> None:
        """移除玩家，并保持座位顺序连续。"""
        try:
            self.player_list.pop(self.id_2_player[user_id].order)
        except KeyError:
            await self.broadcast(f"玩家 {user_id} 不存在于房间内")
            return
        for i in self.player_list[self.id_2_player[user_id].order :]:
            i.order -= 1
        del self.id_2_player[user_id]

    async def add_character(self, character_list: list[str]) -> None:
        """按别名启用角色（例如：`狼`、`seer`）。"""
        added_aliases: list[str] = []
        unknown_aliases: list[str] = []
        for alias in character_list:
            alias = alias.strip()
            if not alias:
                continue
            role_cls = get_character_class_by_alias(alias)
            if not role_cls:
                unknown_aliases.append(alias)
                continue
            self.character_enabled[role_cls] = (
                self.character_enabled.get(role_cls, 0) + 1
            )
            added_aliases.append(alias)

        lines: list[str] = []
        if added_aliases:
            lines.append(f"添加了角色: {', '.join(added_aliases)}")
        if unknown_aliases:
            lines.append(f"未知角色别名: {', '.join(unknown_aliases)}")
        if not lines:
            lines.append("没有添加任何角色")
        await self.broadcast("\n".join(lines))

    async def remove_character(self, character_list: list[str]) -> None:
        """按别名移除已启用角色。"""
        removed_aliases: list[str] = []
        unknown_aliases: list[str] = []
        not_enabled: list[str] = []
        for alias in character_list:
            alias = alias.strip()
            if not alias:
                continue
            role_cls = get_character_class_by_alias(alias)
            if not role_cls:
                unknown_aliases.append(alias)
                continue
            if role_cls not in self.character_enabled:
                not_enabled.append(alias)
                continue
            self.character_enabled[role_cls] -= 1
            if self.character_enabled[role_cls] <= 0:
                del self.character_enabled[role_cls]
            removed_aliases.append(alias)

        lines: list[str] = []
        if removed_aliases:
            lines.append(f"移除了角色: {', '.join(removed_aliases)}")
        if not_enabled:
            lines.append(f"未启用角色别名: {', '.join(not_enabled)}")
        if unknown_aliases:
            lines.append(f"未知角色别名: {', '.join(unknown_aliases)}")
        if not lines:
            lines.append("没有移除任何角色")
        await self.broadcast("\n".join(lines))

    def change_setting(self, key: str, value: int | str | bool):
        """修改房间设置（预留扩展）。"""
        self.settings[key] = value

    def _register_core_event_listeners(self) -> None:
        """注册与角色无关的核心流程监听器。

        注意：每次开局都会重建 `EventSystem`，因此这里不会产生重复注册。
        """
        es = self.events_system

        es.event_game_start.add_listener(self._on_game_start, priority=0)
        es.event_game_start.add_listener(self._on_game_start_to_night_start, priority=-10)

        es.event_night_start.add_listener(self._on_night_start, priority=0)
        es.event_night_start.add_listener(
            self._on_night_start_kick_night_end, priority=-10
        )

        es.event_wolf_locked.add_listener(self._on_wolf_locked, priority=0)

        es.event_night_end.add_listener(self._on_night_end_resolve, priority=0)
        es.event_night_end.add_listener(self._on_night_end_to_day_start, priority=-10)

        es.event_person_killed.add_listener(
            self._on_person_killed_bridge_next_event, priority=-10
        )

        es.event_day_start.add_listener(self._on_day_start, priority=0)

        es.event_vote_start.add_listener(self._on_vote_start, priority=0)
        es.event_vote.add_listener(self._on_vote_input, priority=0)
        es.event_skip.add_listener(self._on_skip_input, priority=0)

        es.event_vote_end.add_listener(self._on_vote_end_resolve, priority=0)
        es.event_vote_end.add_listener(self._on_vote_end_to_day_end, priority=-10)

        es.event_day_end.add_listener(self._on_day_end, priority=0)
        es.event_game_end.add_listener(self._on_game_end, priority=0)

    async def GameStart(self) -> None:
        """游戏开始：分配身份并触发 `game_start` 事件。"""
        if self.state != "lobby":
            await self.broadcast("游戏已开始，无法重复开始。")
            return
        if len(self.player_list) < 4:
            await self.broadcast("玩家人数不足 (至少 4 人) 。")
            return

        # 重置对局运行时状态
        self.events_system = EventSystem()
        self._pending_death_records = []
        self.vote_pending_user_ids = set()
        for p in self.player_list:
            p.alive = True
            p.role = None
        self.votes = {}
        self.day_count = 0
        self.day_speech_order_user_ids = []
        self.day_speech_index = 0

        role_pool: list[type[CharacterBase]] = []
        for cls, count in self.character_enabled.items():
            if count <= 0:
                continue
            role_pool.extend([cls] * count)
        if len(role_pool) > len(self.player_list):
            await self.broadcast("已添加的角色数量超过玩家人数，请先删角色。")
            return
        if len(role_pool) < len(self.player_list):
            role_pool.extend(
                [CharacterPerson] * (len(self.player_list) - len(role_pool))
            )

        if not any(getattr(cls, "camp", None) == "wolf" for cls in role_pool):
            await self.broadcast("至少需要 1 个狼人角色。")
            return

        random.shuffle(role_pool)
        for player, role_cls in zip(self.player_list, role_pool):
            player.role = role_cls(self, player)

        seats_text = " ".join(
            f"{p.seat}号 [CQ:at,qq={int(p.user_id)}]" for p in self.player_list
        )
        await self.broadcast(f"游戏开始！座位顺序: {seats_text}")

        for p in self.player_list:
            if not p.role:
                continue
            camp_name = "狼人阵营" if p.role.camp == "wolf" else "好人阵营"
            await self.post_to_player(
                p.user_id,
                f"你的编号: {p.seat}号\n你的身份: {p.role.name} ({camp_name}) ",
            )

        # 注册核心监听器（在触发 game_start 事件前完成）
        self._register_core_event_listeners()
        await self.events_system.event_game_start.active(self, None, [])

    async def start_game(self) -> None:
        """兼容旧接口：等价于 `GameStart()`。"""
        await self.GameStart()

    def get_player_by_seat(self, seat: int) -> Player | None:
        """按 1 基座位号获取玩家。"""
        if seat < 1 or seat > len(self.player_list):
            return None
        return self.player_list[seat - 1]

    def alive_players(self) -> list[Player]:
        """按座位顺序返回存活玩家列表。"""
        return [p for p in self.player_list if p.alive]

    def alive_user_ids(self) -> set[str]:
        """返回所有存活玩家的 user_id。"""
        return {p.user_id for p in self.alive_players()}

    def alive_role_user_ids(self, role_id: str) -> set[str]:
        """返回指定 `role_id` 的存活玩家 user_id 集合。"""
        return {
            p.user_id
            for p in self.player_list
            if p.alive and p.role and p.role.role_id == role_id
        }

    # === 事件驱动：核心流程监听器实现 ===

    async def _on_game_start(self, room: object, user_id: str | None, args: list[str]) -> None:
        """游戏开始事件：这里只做最小处理，真正推进由桥接监听器完成。"""
        return

    async def _on_game_start_to_night_start(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """桥接：game_start -> night_start（使用 lock/unlock 触发）。"""
        self.events_system.event_night_start.lock()
        await self.events_system.event_night_start.unlock(self, None, [])

    async def _on_night_start(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """夜晚开始：重置夜晚运行时状态并广播提示。"""
        self.state = "night"

        self.night_kill_votes = {}
        self.night_wolf_done_user_ids = set()
        self.night_kill_target_user_id = None
        self.night_kill_locked = False
        self._night_wolf_locked_event_fired = False
        self.night_seer_done_user_ids = set()
        self.last_night_death_user_ids = []

        self.night_guard_target_by_user_id = {}
        self.night_guard_done_user_ids = set()

        self.night_witch_done_user_ids = set()
        self.night_witch_saved = False
        self.night_witch_poison_target_by_user_id = {}

        self._pending_death_records = []

        await self.broadcast("天黑请闭眼。")

    async def _on_night_start_kick_night_end(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """兜底推进：night_start 结束时，踢一次 night_end（避免无锁时流程卡死）。"""
        self.events_system.event_night_end.lock()
        await self.events_system.event_night_end.unlock(self, None, [])

    async def _on_wolf_locked(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """狼人刀口锁定事件：默认不处理（女巫等角色可监听此事件）。"""
        return

    async def _on_night_end_resolve(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """夜晚结束：结算夜晚行动并记录死亡列表（不在此处推进到下一事件）。"""
        if self.state != "night":
            return

        self._pending_death_records = []

        victims: list[tuple[Player, str]] = []

        protected = set(self.night_guard_target_by_user_id.values())
        for guard_id, target_id in self.night_guard_target_by_user_id.items():
            self.guard_last_target_by_user_id[guard_id] = target_id

        if self.night_kill_target_user_id and not self.night_witch_saved:
            if self.night_kill_target_user_id not in protected:
                victim = self.id_2_player.get(self.night_kill_target_user_id)
                if victim and victim.alive:
                    victims.append((victim, "夜晚被狼人击杀"))

        for target_id in set(self.night_witch_poison_target_by_user_id.values()):
            victim = self.id_2_player.get(target_id)
            if victim and victim.alive:
                if all(v.user_id != victim.user_id for v, _ in victims):
                    victims.append((victim, "夜晚被女巫毒杀"))

        for victim, reason in victims:
            await self.kill_player(victim, reason)
            self._pending_death_records.append((victim.user_id, reason))
            self.last_night_death_user_ids.append(victim.user_id)

        if not victims:
            await self.broadcast("天亮了：昨晚是平安夜。")
        else:
            seats = "、".join(f"{p.seat}号" for p, _ in victims)
            await self.broadcast(f"天亮了：昨晚 {seats} 死亡。")

    async def _on_night_end_to_day_start(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """桥接：night_end -> person_killed -> day_start（确保在最后执行）。"""
        if self._pending_death_records:
            for index, (victim_user_id, reason) in enumerate(
                self._pending_death_records
            ):
                death_args = [reason]
                if index == len(self._pending_death_records) - 1:
                    death_args.append("day_start")
                await self.events_system.event_person_killed.active(
                    self, victim_user_id, death_args
                )
            self._pending_death_records = []
            return

        self.events_system.event_day_start.lock()
        await self.events_system.event_day_start.unlock(self, None, [])

    async def _on_person_killed_bridge_next_event(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """桥接：person_killed -> next_event。

        约定：
        - args[0]：死亡原因
        - args[1]：下一事件名称（可选）
        """
        if len(args) < 2:
            return
        next_event_name = args[1].strip()
        if not next_event_name:
            return
        next_event = self.events_system.get_or_create_event(next_event_name)
        next_event.lock()
        await next_event.unlock(self, None, [])

    async def _on_day_start(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """白天开始：检查终局；若未结束则进入轮流发言。"""
        winner = self.check_winner()
        if winner:
            await self.events_system.event_game_end.active(self, None, [winner])
            return

        self.state = "speech"
        self.day_count += 1
        self.day_speech_order_user_ids = [p.user_id for p in self.player_list if p.alive]
        ascending = self.day_count % 2 == 1
        if not ascending:
            self.day_speech_order_user_ids.reverse()
        self.day_speech_index = 0

        if not self.day_speech_order_user_ids:
            await self.broadcast("无人存活，游戏结束。")
            await self.events_system.event_game_end.active(self, None, ["good"])
            return

        first = self.id_2_player[self.day_speech_order_user_ids[0]]
        direction = "从小到大" if ascending else "从大到小"
        await self.broadcast(
            f"白天发言阶段开始（第{self.day_count}天）：按编号顺序依次发言（{direction}）。\n"
            f"请 {first.seat}号 发言。发言结束后发送 `/wft skip` 进入下一位。"
        )

    async def _on_vote_start(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """开始投票：初始化投票数据，并锁定 vote_end 等待所有存活玩家回应。"""
        self.state = "vote"
        self.votes = {}
        alive = self.alive_user_ids()
        self.vote_pending_user_ids = set(alive)

        for _ in range(len(self.vote_pending_user_ids)):
            self.events_system.event_vote_end.lock()

        await self.broadcast(
            "投票阶段开始：请发送 `/wft vote <编号>` 投票，或发送 `/wft skip` 弃票。"
        )

        # 极端情况下（无人存活）直接触发 vote_end
        if not self.vote_pending_user_ids:
            await self.events_system.event_vote_end.unlock(self, None, [])

    async def _on_vote_input(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """玩家投票输入：记录投票并在首次回应时解锁 vote_end。"""
        if not user_id or self.state != "vote":
            return
        voter = self.id_2_player.get(user_id)
        if not voter or not voter.alive:
            return
        if not args or not args[0].isdigit():
            return

        seat = int(args[0])
        target = self.get_player_by_seat(seat)
        if not target or not target.alive:
            return

        self.votes[user_id] = target.user_id
        await self.broadcast(f"{voter.seat}号 投票给 {target.seat}号。")

        if user_id in self.vote_pending_user_ids:
            self.vote_pending_user_ids.remove(user_id)
            await self.events_system.event_vote_end.unlock(self, user_id, [])

    async def _on_skip_input(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """玩家跳过输入：用于白天发言推进/投票弃票；夜晚跳过交给角色监听器处理。"""
        if not user_id:
            return

        if self.state == "speech":
            await self._handle_speech_skip(user_id)
            return

        if self.state == "vote":
            await self._handle_vote_skip(user_id)
            return

        # night/lobby/ended：这里不处理，让角色/上层决定
        return

    async def _handle_speech_skip(self, user_id: str) -> None:
        current_id = self.current_speaker_user_id()
        if not current_id:
            return
        if user_id != current_id:
            current_player = self.id_2_player.get(current_id)
            if current_player:
                await self.broadcast(f"还没轮到你发言。当前请 {current_player.seat}号 发言。")
            return

        self.day_speech_index += 1
        if self.day_speech_index >= len(self.day_speech_order_user_ids):
            await self.broadcast("发言结束，开始投票。")
            await self.events_system.event_vote_start.active(self, None, [])
            return

        next_id = self.day_speech_order_user_ids[self.day_speech_index]
        next_player = self.id_2_player.get(next_id)
        if next_player:
            await self.broadcast(f"请 {next_player.seat}号 发言。发言结束后发送 `/wft skip`。")

    async def _handle_vote_skip(self, user_id: str) -> None:
        voter = self.id_2_player.get(user_id)
        if not voter or not voter.alive:
            return

        self.votes[user_id] = None
        await self.broadcast(f"{voter.seat}号 弃票。")

        if user_id in self.vote_pending_user_ids:
            self.vote_pending_user_ids.remove(user_id)
            await self.events_system.event_vote_end.unlock(self, user_id, [])

    async def _on_vote_end_resolve(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """结束投票：结算放逐并记录死亡（不在此处推进到下一事件）。"""
        if self.state != "vote":
            return

        self._pending_death_records = []

        counts = Counter(v for v in self.votes.values() if v)
        if not counts:
            await self.broadcast("投票结束：无人被放逐。")
            return

        most_common = counts.most_common()
        top_target, top_count = most_common[0]
        if len(most_common) > 1 and most_common[1][1] == top_count:
            await self.broadcast("投票结束：票数相同，无人被放逐。")
            return

        target_player = self.id_2_player.get(top_target)
        if target_player and target_player.alive:
            await self.kill_player(target_player, "白天投票放逐")
            await self.broadcast(f"投票结束：{target_player.seat}号 被放逐。")
            self._pending_death_records.append((target_player.user_id, "白天投票放逐"))
        else:
            await self.broadcast("投票结束：目标无效，无人被放逐。")

    async def _on_vote_end_to_day_end(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """桥接：vote_end -> person_killed -> day_end（确保在最后执行）。"""
        if self._pending_death_records:
            for index, (victim_user_id, reason) in enumerate(
                self._pending_death_records
            ):
                death_args = [reason]
                if index == len(self._pending_death_records) - 1:
                    death_args.append("day_end")
                await self.events_system.event_person_killed.active(
                    self, victim_user_id, death_args
                )
            self._pending_death_records = []
            return

        self.events_system.event_day_end.lock()
        await self.events_system.event_day_end.unlock(self, None, [])

    async def _on_day_end(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """白天结束：检查终局；若未结束则进入下一夜。"""
        winner = self.check_winner()
        if winner:
            await self.events_system.event_game_end.active(self, None, [winner])
            return

        self.events_system.event_night_start.lock()
        await self.events_system.event_night_start.unlock(self, None, [])

    async def _on_game_end(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """终局：广播胜负并结束对局。"""
        winner = args[0] if args else None
        if winner == "good":
            await self.broadcast("游戏结束：好人胜利！")
        elif winner == "wolf":
            await self.broadcast("游戏结束：狼人胜利！")
        else:
            await self.broadcast("游戏结束。")

        self.state = "ended"

    async def kill_player(self, player: Player, reason: str) -> None:
        """标记玩家死亡（不在此处触发 `person_killed` 事件）。

        说明：死亡事件的触发由流程事件（如 `night_end` / `vote_end`）统一控制，
        以便携带“下一事件”参数并确保触发顺序正确。
        """
        if not player.alive:
            return
        player.alive = False
        await self.post_to_player(player.user_id, f"你已死亡 ({reason}) 。")

    def check_winner(self) -> str | None:
        """若已分胜负返回 `good` 或 `wolf`，否则返回 None。"""
        alive = self.alive_players()
        wolves = [p for p in alive if p.role and p.role.camp == "wolf"]
        goods = [p for p in alive if not (p.role and p.role.camp == "wolf")]
        if not wolves:
            return "good"
        if len(wolves) >= len(goods):
            return "wolf"
        return None

    def current_speaker_user_id(self) -> str | None:
        """在白天发言阶段返回当前发言者的 user_id。"""
        if self.state != "speech":
            return None
        if self.day_speech_index < 0 or self.day_speech_index >= len(
            self.day_speech_order_user_ids
        ):
            return None
        return self.day_speech_order_user_ids[self.day_speech_index]

    async def start_vote(self) -> None:
        """兼容旧接口：进入投票阶段（事件驱动）。"""
        if self.state == "ended":
            return
        await self.events_system.event_vote_start.active(self, None, [])

    async def cast_vote(self, voter_user_id: str, seat: int) -> tuple[bool, str]:
        """兼容旧接口：投票输入（事件驱动）。"""
        if self.state != "vote":
            return False, "现在不是投票阶段。"
        voter = self.id_2_player.get(voter_user_id)
        if not voter or not voter.alive:
            return False, "你不在游戏中，或已死亡。"
        target = self.get_player_by_seat(seat)
        if not target:
            return False, "目标编号无效。"
        if not target.alive:
            return False, "目标已死亡，无法投票。"

        await self.events_system.event_vote.active(self, voter_user_id, [str(seat)])
        return True, "投票成功。"

    async def skip(self, user_id: str) -> tuple[bool, str]:
        """兼容旧接口：跳过/结束发言/弃票/放弃技能（事件驱动）。"""
        player = self.id_2_player.get(user_id)
        if not player or not player.alive:
            return False, "你不在游戏中，或已死亡。"

        await self.events_system.event_skip.active(self, user_id, [])
        return True, "已处理。"
