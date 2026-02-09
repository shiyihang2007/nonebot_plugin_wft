"""nonebot_plugin_wft 的房间状态机与核心游戏循环。

本模块实现了一个最小可玩的经典狼人杀流程：

- lobby：创建房间、加入/退出、配置角色
- night：狼人击杀；预言家查验；守卫守护；女巫救人/毒人
- day：白天发言阶段（按座位顺序依次发言，每天翻转方向）
- vote：放逐投票
- ended：胜负判定（无狼人则好人胜；狼人数量 >= 好人数则狼人胜）
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

    房间负责保存玩家状态、角色状态与事件系统。游戏开始（`start_game`）时创建角色实例，
    并注册事件监听器；随后通过处理 `/wft skill ...` 与 `/wft skip` 等玩家输入推进流程。
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

        self.state: str = "lobby"  # lobby -> night -> day(speech) -> vote -> ended

        self.day_count: int = 0
        self.day_speech_order_user_ids: list[str] = []
        self.day_speech_index: int = 0

        self.night_kill_votes: dict[str, str] = {}
        self.night_wolf_done_user_ids: set[str] = set()
        self.night_kill_target_user_id: str | None = None
        self.night_kill_locked: bool = False
        self.night_seer_done_user_ids: set[str] = set()

        self.night_guard_target_by_user_id: dict[str, str] = {}
        self.guard_last_target_by_user_id: dict[str, str] = {}
        self.night_guard_done_user_ids: set[str] = set()

        self.night_witch_done_user_ids: set[str] = set()
        self.night_witch_saved: bool = False
        self.night_witch_poison_target_by_user_id: dict[str, str] = {}

        self.votes: dict[str, str | None] = {}
        self.last_night_death_user_ids: list[str] = []

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

    async def start_game(self) -> None:
        """分配角色并进入第一个夜晚。"""
        if self.state != "lobby":
            await self.broadcast("游戏已开始，无法重复开始。")
            return
        if len(self.player_list) < 4:
            await self.broadcast("玩家人数不足 (至少 4 人) 。")
            return

        # reset runtime state
        self.events_system = EventSystem()
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

        await self.start_night()

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

    async def start_night(self) -> None:
        """进入夜晚阶段并触发角色提示。"""
        if self.state == "ended":
            return
        self.state = "night"
        self.night_kill_votes = {}
        self.night_wolf_done_user_ids = set()
        self.night_kill_target_user_id = None
        self.night_kill_locked = False
        self.night_seer_done_user_ids = set()
        self.last_night_death_user_ids = []

        self.night_guard_target_by_user_id = {}
        self.night_guard_done_user_ids = set()

        self.night_witch_done_user_ids = set()
        self.night_witch_saved = False
        self.night_witch_poison_target_by_user_id = {}

        await self.broadcast("天黑请闭眼。")
        await self.events_system.event_night_start.active(self, None, [])
        await self.try_advance()

    def _lock_night_kill_if_possible(self) -> None:
        """尝试锁定狼刀结果。

        最小规则：
        - 若某个目标获得严格多数票（> 存活狼人一半）：立即锁定击杀该目标。
        - 否则当所有狼人都已回应（投票或跳过）：锁定为“本夜无人死亡”。
        """
        if self.night_kill_locked:
            return
        wolves = self.alive_role_user_ids("wolf")
        if not wolves:
            self.night_kill_locked = True
            self.night_kill_target_user_id = None
            return

        votes = {uid: self.night_kill_votes.get(uid) for uid in wolves}
        votes = {uid: v for uid, v in votes.items() if v}

        if votes:
            counts = Counter(votes.values())
            top_target, top_count = counts.most_common(1)[0]
            if top_count > len(wolves) / 2:
                self.night_kill_locked = True
                self.night_kill_target_user_id = top_target
                return

        if wolves.issubset(self.night_wolf_done_user_ids):
            self.night_kill_locked = True
            self.night_kill_target_user_id = None

    async def wolf_vote_kill(self, wolf_user_id: str, seat: int) -> tuple[bool, str]:
        """记录狼人本夜的击杀投票。"""
        if self.state != "night":
            return False, "现在不是夜晚阶段。"
        if self.night_kill_locked:
            return False, "狼人行动已锁定。"
        wolf_player = self.id_2_player.get(wolf_user_id)
        if not wolf_player or not wolf_player.alive:
            return False, "你不在游戏中，或已死亡。"
        if not wolf_player.role or wolf_player.role.role_id != "wolf":
            return False, "你不是狼人。"

        target = self.get_player_by_seat(seat)
        if not target:
            return False, "目标编号无效。"
        if not target.alive:
            return False, "目标已死亡。"
        if target.user_id == wolf_user_id:
            return False, "不能选择自己作为击杀目标。"

        self.night_kill_votes[wolf_user_id] = target.user_id
        self.night_wolf_done_user_ids.add(wolf_user_id)
        self._lock_night_kill_if_possible()
        if self.night_kill_locked:
            if self.night_kill_target_user_id:
                victim = self.id_2_player[self.night_kill_target_user_id]
                await self._notify_witches_of_attack(victim)
                return True, f"已投票击杀 {victim.seat}号。狼人行动已锁定。"
            return True, "已投票。狼人行动已锁定: 本夜无人死亡 (票型未达成多数) 。"
        return True, f"已投票击杀 {target.seat}号。"

    async def _notify_witches_of_attack(self, victim: Player) -> None:
        """通知存活女巫当前已锁定的狼刀目标（用于决定是否用解药）。"""
        witches = [
            p
            for p in self.player_list
            if p.alive and p.role and p.role.role_id == "witch"
        ]
        if not witches:
            return
        for w in witches:
            await self.post_to_player(
                w.user_id,
                f"女巫提示: 狼刀落在 {victim.seat}号。\n"
                "你可以使用 `/wft skill save` 使用解药救人，或 `/wft skip` 放弃本夜行动。",
            )

    async def guard_protect(self, guard_user_id: str, seat: int) -> tuple[bool, str]:
        """守卫选择本夜的守护目标。"""
        if self.state != "night":
            return False, "现在不是夜晚阶段。"
        guard_player = self.id_2_player.get(guard_user_id)
        if not guard_player or not guard_player.alive:
            return False, "你不在游戏中，或已死亡。"
        if not guard_player.role or guard_player.role.role_id != "guard":
            return False, "你不是守卫。"

        target = self.get_player_by_seat(seat)
        if not target:
            return False, "目标编号无效。"
        if not target.alive:
            return False, "目标已死亡。"

        last = self.guard_last_target_by_user_id.get(guard_user_id)
        if last and last == target.user_id:
            return False, "不能连续两晚守护同一名玩家。"

        self.night_guard_target_by_user_id[guard_user_id] = target.user_id
        self.night_guard_done_user_ids.add(guard_user_id)
        return True, f"你将守护 {target.seat}号。"

    async def witch_save(self, witch_user_id: str) -> tuple[bool, str]:
        """女巫使用解药取消本夜狼刀。"""
        if self.state != "night":
            return False, "现在不是夜晚阶段。"
        witch_player = self.id_2_player.get(witch_user_id)
        if not witch_player or not witch_player.alive:
            return False, "你不在游戏中，或已死亡。"
        if not witch_player.role or witch_player.role.role_id != "witch":
            return False, "你不是女巫。"
        if self.night_witch_saved:
            return False, "本夜已使用过解药。"
        if not self.night_kill_target_user_id:
            return False, "当前没有可救的人 (狼刀未确定或本夜平安) 。"
        self.night_witch_saved = True
        self.night_witch_done_user_ids.add(witch_user_id)
        victim = self.id_2_player.get(self.night_kill_target_user_id)
        if victim:
            return True, f"你使用了解药，救下了 {victim.seat}号。"
        return True, "你使用了解药。"

    async def witch_poison(self, witch_user_id: str, seat: int) -> tuple[bool, str]:
        """女巫对玩家下毒（额外的夜晚死亡）。"""
        if self.state != "night":
            return False, "现在不是夜晚阶段。"
        witch_player = self.id_2_player.get(witch_user_id)
        if not witch_player or not witch_player.alive:
            return False, "你不在游戏中，或已死亡。"
        if not witch_player.role or witch_player.role.role_id != "witch":
            return False, "你不是女巫。"

        target = self.get_player_by_seat(seat)
        if not target:
            return False, "目标编号无效。"
        if not target.alive:
            return False, "目标已死亡。"
        if target.user_id == witch_user_id:
            return False, "不能对自己使用毒药。"
        if witch_user_id in self.night_witch_poison_target_by_user_id:
            return False, "你本夜已经使用过毒药。"

        self.night_witch_poison_target_by_user_id[witch_user_id] = target.user_id
        self.night_witch_done_user_ids.add(witch_user_id)
        return True, f"你对 {target.seat}号 使用了毒药。"

    def seer_check(self, seat: int) -> tuple[bool, str]:
        """返回预言家对指定座位的查验结果文本（狼人/好人）。"""
        target = self.get_player_by_seat(seat)
        if not target:
            return False, "目标编号无效。"
        if not target.alive:
            return False, "目标已死亡。"
        if not target.role:
            return False, "目标身份未知。"
        result = "狼人" if target.role.camp == "wolf" else "好人"
        return True, f"查验结果: {target.seat}号 是 {result}。"

    async def kill_player(self, player: Player, reason: str) -> None:
        """标记玩家死亡并触发 `person_killed` 事件。"""
        if not player.alive:
            return
        player.alive = False
        await self.post_to_player(player.user_id, f"你已死亡 ({reason}) 。")
        await self.events_system.event_person_killed.active(
            self, player.user_id, [reason]
        )

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

    async def resolve_night(self) -> None:
        """结算夜晚行动并进入白天发言。"""
        if self.state != "night":
            return

        victims: list[Player] = []

        protected = set(self.night_guard_target_by_user_id.values())
        for guard_id, target_id in self.night_guard_target_by_user_id.items():
            self.guard_last_target_by_user_id[guard_id] = target_id

        if self.night_kill_target_user_id and not self.night_witch_saved:
            if self.night_kill_target_user_id not in protected:
                victim = self.id_2_player.get(self.night_kill_target_user_id)
                if victim and victim.alive:
                    victims.append(victim)

        for target_id in set(self.night_witch_poison_target_by_user_id.values()):
            victim = self.id_2_player.get(target_id)
            if victim and victim.alive and victim not in victims:
                victims.append(victim)

        for v in victims:
            reason = "夜晚死亡"
            if (
                v.user_id == self.night_kill_target_user_id
                and not self.night_witch_saved
            ):
                reason = "夜晚被狼人击杀"
            if v.user_id in self.night_witch_poison_target_by_user_id.values():
                reason = "夜晚被女巫毒杀"
            await self.kill_player(v, reason)
            self.last_night_death_user_ids.append(v.user_id)

        self.state = "day"
        if not victims:
            await self.broadcast("天亮了: 昨晚是平安夜。")
        else:
            seats = "、".join(f"{p.seat}号" for p in victims)
            await self.broadcast(f"天亮了: 昨晚 {seats} 死亡。")
        await self.events_system.event_day_start.active(self, None, [])

        winner = self.check_winner()
        if winner:
            await self.broadcast(
                "游戏结束: " + ("好人胜利！" if winner == "good" else "狼人胜利！")
            )
            self.state = "ended"
            return

        await self.start_day_speech()

    async def start_day_speech(self) -> None:
        """开始白天发言阶段。

        发言顺序按座位号排列；每隔一天翻转一次方向。
        """
        if self.state == "ended":
            return
        self.state = "day"
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
            self.state = "ended"
            return

        first = self.id_2_player[self.day_speech_order_user_ids[0]]
        direction = "从小到大" if ascending else "从大到小"
        await self.broadcast(
            f"白天发言阶段开始 (第{self.day_count}天) : 按编号顺序依次发言 ({direction}) 。\n"
            f"请 {first.seat}号 发言。发言结束后发送 `/wft skip` 进入下一位。"
        )

    def current_speaker_user_id(self) -> str | None:
        """在白天发言阶段返回当前发言者的 user_id。"""
        if self.state != "day":
            return None
        if self.day_speech_index < 0 or self.day_speech_index >= len(
            self.day_speech_order_user_ids
        ):
            return None
        return self.day_speech_order_user_ids[self.day_speech_index]

    async def end_speech_turn(self, user_id: str) -> tuple[bool, str]:
        """结束当前发言并轮到下一位（仅当前发言者可调用）。"""
        if self.state != "day":
            return False, "现在不是发言阶段。"
        current_id = self.current_speaker_user_id()
        if not current_id:
            return False, "发言阶段状态异常。"
        if user_id != current_id:
            current_player = self.id_2_player.get(current_id)
            if current_player:
                return False, f"还没轮到你发言。当前请 {current_player.seat}号 发言。"
            return False, "还没轮到你发言。"

        current_player = self.id_2_player.get(current_id)
        self.day_speech_index += 1
        if self.day_speech_index >= len(self.day_speech_order_user_ids):
            await self.broadcast("发言结束，开始投票。")
            await self.start_vote()
            return True, "你已结束发言，进入投票。"

        next_id = self.day_speech_order_user_ids[self.day_speech_index]
        next_player = self.id_2_player.get(next_id)
        if current_player and next_player:
            await self.broadcast(
                f"{current_player.seat}号 发言结束。请 {next_player.seat}号 发言。"
            )
        elif next_player:
            await self.broadcast(f"请 {next_player.seat}号 发言。")
        else:
            await self.broadcast("发言顺序异常，直接进入投票。")
            await self.start_vote()
        return True, "你已结束发言。"

    async def start_vote(self) -> None:
        """进入投票阶段并提示玩家投票。"""
        if self.state == "ended":
            return
        self.state = "vote"
        self.votes = {}
        await self.broadcast(
            "现在开始投票: 使用 `/wft vote <编号>` 投票，或 `/wft skip` 弃票。"
        )
        await self.events_system.event_vote_start.active(self, None, [])
        await self.try_advance()

    async def cast_vote(self, voter_user_id: str, seat: int) -> tuple[bool, str]:
        """在投票阶段对存活目标投票/改票。"""
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

        self.votes[voter_user_id] = target.user_id
        await self.broadcast(f"{voter.seat}号 投票给 {target.seat}号。")
        return True, "投票成功。"

    async def skip(self, user_id: str) -> tuple[bool, str]:
        """跳过当前需要的操作（夜晚行动/发言/投票）。"""
        player = self.id_2_player.get(user_id)
        if not player or not player.alive:
            return False, "你不在游戏中，或已死亡。"

        if self.state == "day":
            return await self.end_speech_turn(user_id)

        if self.state == "night":
            if not player.role:
                return False, "你还没有身份。"
            if player.role.role_id == "wolf":
                if self.night_kill_locked:
                    return False, "狼人行动已锁定。"
                self.night_wolf_done_user_ids.add(user_id)
                self._lock_night_kill_if_possible()
                return True, "你已放弃本夜击杀投票。"
            if player.role.role_id == "seer":
                self.night_seer_done_user_ids.add(user_id)
                return True, "你已放弃本夜查验。"
            if player.role.role_id == "guard":
                self.night_guard_done_user_ids.add(user_id)
                return True, "你已放弃本夜守护。"
            if player.role.role_id == "witch":
                self.night_witch_done_user_ids.add(user_id)
                return True, "你已放弃本夜用药。"
            return False, "你没有需要跳过的夜晚行动。"

        if self.state == "vote":
            self.votes[user_id] = None
            await self.broadcast(f"{player.seat}号 弃票。")
            return True, "弃票成功。"

        return False, "当前阶段不支持跳过。"

    async def resolve_vote(self) -> None:
        """结算放逐投票并进入下一夜（或结束游戏）。"""
        if self.state != "vote":
            return

        counts = Counter(v for v in self.votes.values() if v)
        if not counts:
            await self.broadcast("投票结束: 无人被放逐。")
            await self.start_night()
            return

        most_common = counts.most_common()
        top_target, top_count = most_common[0]
        if len(most_common) > 1 and most_common[1][1] == top_count:
            await self.broadcast("投票结束: 票数相同，无人被放逐。")
            await self.start_night()
            return

        target_player = self.id_2_player.get(top_target)
        if target_player and target_player.alive:
            await self.kill_player(target_player, "白天投票放逐")
            await self.broadcast(f"投票结束: {target_player.seat}号 被放逐。")
        else:
            await self.broadcast("投票结束: 目标无效，无人被放逐。")

        winner = self.check_winner()
        if winner:
            await self.broadcast(
                "游戏结束: " + ("好人胜利！" if winner == "good" else "狼人胜利！")
            )
            self.state = "ended"
            return

        await self.start_night()

    async def try_advance(self) -> None:
        """若当前阶段所需操作已全部完成，则推进状态机。"""
        if self.state == "night":
            self._lock_night_kill_if_possible()
            seers = self.alive_role_user_ids("seer")
            seers_done = not seers or seers.issubset(self.night_seer_done_user_ids)
            guards = self.alive_role_user_ids("guard")
            guards_done = not guards or guards.issubset(self.night_guard_done_user_ids)
            witches = self.alive_role_user_ids("witch")
            witches_done = not witches or witches.issubset(
                self.night_witch_done_user_ids
            )
            wolves_done = not self.alive_role_user_ids("wolf") or self.night_kill_locked
            if wolves_done and seers_done and guards_done and witches_done:
                await self.resolve_night()
            return

        if self.state == "vote":
            alive = self.alive_user_ids()
            if alive and alive.issubset(set(self.votes.keys())):
                await self.resolve_vote()
