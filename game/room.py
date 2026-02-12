"""nonebot_plugin_wft 的房间对象与对局流程控制（事件驱动）。

本版本不再通过“显式状态机函数链（start_xxx/resolve_xxx/try_advance）”推进流程，
而是由 `EventSystem` + `EventBase.lock/unlock` 控制对局事件的触发顺序与等待点。

对照 `docs/wft_event_graph.md` 的关键事件（简化命名）：

- `game_start`：游戏开始
- `night_start`：夜晚开始
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
        # - start：开始中
        # - night：夜晚（私聊技能/跳过）
        # - speech：白天轮流发言（群聊 skip 推进）
        # - vote：白天投票（群聊 vote/skip）
        # - ended：终局
        self.state: str = "lobby"

        self.day_count: int = 0
        self.day_speech_order_user_ids: list[str] = []
        self.day_speech_index: int = 0

        self.votes: dict[str, str | None] = {}

        # 事件驱动流程的运行时状态（尽量保持“可扩展”且不耦合具体角色实现）。
        self.pending_death_records: dict[str, str] = {}  # (user_id, reason)
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
            lines.append(f"角色不存在: {', '.join(not_enabled)}")
        if unknown_aliases:
            lines.append(f"未知角色: {', '.join(unknown_aliases)}")
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

        es.event_game_start.add_listener(self._on_game_start, priority=-10)

        es.event_night_start.add_listener(self._on_night_start, priority=10)
        es.event_night_start.add_listener(
            self._on_night_start_kick_night_end, priority=-10
        )
        es.event_night_end.add_listener(self._on_night_end, priority=-10)
        es.event_day_start.add_listener(self._on_day_start, priority=0)
        es.event_vote_start.add_listener(self._on_vote_start, priority=0)
        es.event_vote.add_listener(self._on_vote_input, priority=0)
        es.event_skip.add_listener(self._on_skip_input_speech, priority=0)
        es.event_skip.add_listener(self._on_skip_input_vote, priority=0)

        es.event_vote_end.add_listener(self._on_vote_end, priority=0)

        es.event_day_end.add_listener(self._on_day_end, priority=0)
        es.event_game_end.add_listener(self._on_game_end, priority=0)

    async def start_game(self) -> None:
        """游戏开始：分配身份并触发 `game_start` 事件。"""
        if self.state != "lobby":
            await self.broadcast("游戏已开始，无法重复开始。")
            return
        if len(self.player_list) < 4:
            if self.settings["debug"]:
                await self.broadcast("警告：调试模式已启用，在人数不足情况下强行开启")
            else:
                await self.broadcast(
                    f"玩家人数不足 (现有 {len(self.player_list)} 人，至少需要 4 人) 。"
                )
                return

        role_pool: list[type[CharacterBase]] = []
        for cls, count in self.character_enabled.items():
            if count <= 0:
                continue
            role_pool.extend([cls] * count)
        if len(role_pool) > len(self.player_list):
            await self.broadcast(
                f"已添加的角色数量({len(role_pool)})超过玩家人数({len(self.player_list)})，请先删除多余角色。"
            )
            return

        if not any(getattr(cls, "camp", None) == "wolf" for cls in role_pool):
            await self.broadcast("至少需要 1 个狼人角色。")
            return

        # 重置对局运行时状态
        self.events_system = EventSystem()
        self.pending_death_records = {}
        self.vote_pending_user_ids = set()
        for p in self.player_list:
            p.alive = True
            p.role = None
        self.votes = {}
        self.day_count = 0
        self.day_speech_order_user_ids = []
        self.day_speech_index = 0

        random.shuffle(role_pool)
        for player, role_cls in zip(self.player_list, role_pool):
            player.role = role_cls(self, player)

        seats_text = "\n".join(
            f"  {p.seat}号 [CQ:at,qq={int(p.user_id)}]" for p in self.player_list
        )
        await self.broadcast(
            f"游戏开始！\n座位顺序: \n{seats_text}\n请在私聊中查收身份牌"
        )
        for p in self.player_list:
            if not p.role:
                continue
            camp_name = "狼人阵营" if p.role.camp == "wolf" else "好人阵营"
            await self.post_to_player(
                p.user_id,
                f"你的编号: {p.seat}号\n你的身份: {p.role.name} ({camp_name}) ",
            )

        self._register_core_event_listeners()
        await self.events_system.event_game_start.active(self, None, [])

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

    async def _on_game_start(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """桥接：game_start -> night_start（使用 lock/unlock 触发）。"""
        logging.debug(
            "监听器被触发: 名称 room._on_game_start, 用途 `桥接：game_start -> night_start`"
        )
        self.events_system.event_night_start.lock()
        await self.events_system.event_night_start.unlock(self, None, [])

    async def _on_night_start(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """夜晚开始：重置夜晚运行时状态并广播提示。"""
        logging.debug(
            "监听器被触发: 名称 room._on_night_start, 用途 `夜晚开始：重置夜晚运行时状态并广播提示`"
        )
        self.state = "night"
        self.pending_death_records = {}
        await self.broadcast("天黑请闭眼。")

    async def _on_night_start_kick_night_end(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """兜底推进：night_start 结束时，踢一次 night_end（避免无锁时流程卡死）。"""
        logging.debug(
            "监听器被触发: 名称 room._on_night_start_kick_night_end, 用途 `兜底推进：night_start 结束时，踢一次 night_end（避免无锁时流程卡死）`"
        )
        self.events_system.event_night_end.lock()
        await self.events_system.event_night_end.unlock(self, None, [])

    async def _on_night_end(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """夜晚结束：结算夜晚行动并发送死亡事件。"""
        logging.debug(
            "监听器被触发: 名称 room._on_night_end, 用途 `夜晚结束：结算夜晚行动并发送死亡事件`"
        )
        if self.state != "night":
            logging.warning("警告: 在不正确的阶段触发了 room._on_night_end")
            return

        # 在死亡事件发送前对 day_start 事件加锁，
        self.events_system.event_day_start.lock()

        victims = [x for x, _ in self.pending_death_records]
        if not victims:
            await self.broadcast("天亮了：昨晚是平安夜。")
        else:
            seats = "、".join(f"{self.id_2_player[p].seat}号" for p in victims)
            await self.broadcast(f"天亮了：昨晚 {seats} 死亡。")
        if self.pending_death_records:
            for victim_user_id, reason in self.pending_death_records:
                await self.events_system.event_person_killed.active(
                    self, victim_user_id, [reason, "day_start"]
                )
            self.pending_death_records = {}
            return
        # 死亡事件发送后尝试解锁以确保在无阻塞时事件流程正常推进
        await self.events_system.event_day_start.unlock(self, None, [])

    async def _on_day_start(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """白天开始：检查终局；若未结束则进入轮流发言。"""
        logging.debug(
            "监听器被触发: 名称 room._on_day_start, 用途 `白天开始：检查终局；若未结束则进入轮流发言`"
        )
        winner = self.check_winner()
        if winner:
            await self.events_system.event_game_end.active(self, None, [winner])
            return

        self.state = "speech"
        self.day_count += 1
        self.day_speech_order_user_ids = [
            p.user_id for p in self.player_list if p.alive
        ]
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
            f"白天发言阶段开始（第{self.day_count}天）：按编号顺序{direction}依次发言。\n"
            f"请 {first.seat}号 发言。发言结束后发送 `/wft skip` 进入下一位。"
        )

    async def _on_skip_input_speech(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """玩家结束发言"""
        logging.debug(
            "监听器被触发: 名称 room._on_skip_input_speech, 用途 `玩家结束发言`"
        )
        if not user_id or self.state != "speech":
            return
        if self.day_speech_index < 0 or self.day_speech_index >= len(
            self.day_speech_order_user_ids
        ):
            return
        current_id = self.day_speech_order_user_ids[self.day_speech_index]
        if user_id != current_id:
            current_player = self.id_2_player.get(current_id)
            if current_player:
                await self.broadcast(
                    f"还没轮到你发言。当前请 {current_player.seat}号 发言。"
                )
            return

        self.day_speech_index += 1
        if self.day_speech_index >= len(self.day_speech_order_user_ids):
            await self.broadcast("发言结束，开始投票。")
            await self.events_system.event_vote_start.active(self, None, [])
            return

        next_id = self.day_speech_order_user_ids[self.day_speech_index]
        next_player = self.id_2_player.get(next_id)
        if next_player:
            await self.broadcast(
                f"请 {next_player.seat}号 发言。发言结束后发送 `/wft skip`。"
            )

    async def _on_vote_start(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """开始投票：初始化投票数据，并锁定 vote_end 等待所有存活玩家回应。"""
        logging.debug(
            "监听器被触发: 名称 room._on_vote_start, 用途 `开始投票：初始化投票数据，并锁定 vote_end 等待所有存活玩家回应`"
        )
        self.state = "vote"
        self.votes = {}
        alive = self.alive_user_ids()
        self.vote_pending_user_ids = set(alive)

        for _ in range(len(self.vote_pending_user_ids)):
            self.events_system.event_vote_end.lock()

        await self.broadcast(
            "投票阶段开始：请发送 `/wft vote <编号>` 投票，或发送 `/wft skip` 弃票。"
        )

    async def _on_vote_input(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """玩家投票输入：记录投票并在首次回应时解锁 vote_end。"""
        logging.debug(
            "监听器被触发: 名称 room._on_vote_input, 用途 `玩家投票输入：记录投票并在首次回应时解锁 vote_end`"
        )
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

    async def _on_skip_input_vote(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """玩家跳过投票"""
        logging.debug(
            "监听器被触发: 名称 room._on_skip_input_vote, 用途 `玩家跳过投票`"
        )
        if not user_id or self.state != "vote":
            return
        voter = self.id_2_player.get(user_id)
        if not voter or not voter.alive:
            return

        self.votes[user_id] = None
        await self.broadcast(f"{voter.seat}号 弃票。")
        if user_id in self.vote_pending_user_ids:
            self.vote_pending_user_ids.remove(user_id)
            await self.events_system.event_vote_end.unlock(self, user_id, [])

    async def _on_vote_end(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """结束投票：结算放逐并发送死亡事件。"""
        logging.debug(
            "监听器被触发: 名称 room._on_vote_end, 用途 `结束投票：结算放逐并发送死亡事件`"
        )
        if self.state != "vote":
            logging.warning(
                "警告: 监听器 room._on_vote_end 在不正确的阶段 `%s` 被触发", self.state
            )
            return

        counts = Counter(v for v in self.votes.values() if v)
        if not counts:
            await self.broadcast("投票结束：无票，无人被放逐。")
            await self.events_system.event_day_end.active(self, None, [])
            return

        most_common = counts.most_common()
        top_target, top_count = most_common[0]
        if len(most_common) > 1 and most_common[1][1] == top_count:
            await self.broadcast("投票结束：票数相同，无人被放逐。")
            await self.events_system.event_day_end.active(self, None, [])
            return

        self.events_system.event_day_end.lock()
        target_player = self.id_2_player.get(top_target)
        if target_player and target_player.alive:
            await self.broadcast(f"投票结束：{target_player.seat}号 被放逐。")
            await self.events_system.event_person_killed.active(
                self, target_player.user_id, ["白天投票放逐", "day_end"]
            )
        else:
            await self.broadcast("投票结束：目标无效，无人被放逐。")

        await self.events_system.event_day_end.unlock(self, None, [])

    async def _on_day_end(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """白天结束：检查终局；若未结束则进入下一夜。"""
        logging.debug(
            "监听器被触发: 名称 room._on_day_end, 用途 `白天结束：检查终局；若未结束则进入下一夜`"
        )
        winner = self.check_winner()
        if winner:
            await self.events_system.event_game_end.active(self, None, [winner])
            return

        await self.events_system.event_night_start.active(self, None, [])

    async def _on_game_end(
        self, room: object, user_id: str | None, args: list[str]
    ) -> None:
        """终局：广播胜负并结束对局。"""
        logging.debug(
            "监听器被触发: 名称 room._on_game_end, 用途 `终局：广播胜负并结束对局`"
        )
        winner = args[0] if args else None
        if winner == "good":
            await self.broadcast("游戏结束：好人胜利！")
        elif winner == "wolf":
            await self.broadcast("游戏结束：狼人胜利！")
        else:
            await self.broadcast("游戏结束。")

        self.state = "ended"

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
