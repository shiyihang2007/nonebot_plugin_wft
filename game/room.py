"""
Room state machine and core game loop for nonebot_plugin_wft.

This module implements a minimal, classic Werewolf ("狼人杀") flow:

- lobby:  create room, join/exit, configure roles
- night:  wolves kill; seer checks; guard protects; witch save/poison
- day:    speech phase (players speak in seat order; flips direction every day)
- vote:   exile vote
- ended:  winner decided (good win if no wolves; wolf win if wolves >= good)
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
    """Load all role classes by importing `character_*.py` modules under this package."""
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
    """Build role_id/alias lookup tables from scanned classes.

    - Enforces `role_id` uniqueness (later duplicates are ignored with a log message).
    - Enforces alias uniqueness (later conflicts are ignored with a log message).
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
    """Resolve a role class by role_id (e.g. 'wolf')."""
    return role_id_2_character_cls.get(role_id)


def get_character_class_by_alias(alias: str) -> type[CharacterBase] | None:
    """Resolve a role class by an alias text (e.g. '狼', 'seer')."""
    return alias_2_character_cls.get(alias)


class Room:
    """A per-group game room (one active game per group_id).

    The room holds player state, role state, and a small event system. Role instances
    register event listeners on creation (start_game) and react to events by handling
    `#wft.skill ...` or `#wft.skip`.
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
        """Send a group message to the room's group."""
        await self.func_send_group_message(group_id=int(self.group_id), message=message)

    async def post_to_player(self, user_id: str, message: str) -> None:
        """Send a private message to a player."""
        await self.func_send_private_message(user_id=int(user_id), message=message)

    async def add_player(self, user_id: str) -> None:
        """Add a player to the room (seat order is join order)."""
        if user_id in self.id_2_player:
            await self.broadcast(f"玩家 {user_id} 已在房间内")
            return
        self.id_2_player[user_id] = Player(user_id, len(self.player_list))
        self.player_list.append(self.id_2_player[user_id])

    async def remove_player(self, user_id: str) -> None:
        """Remove a player and keep seat order continuous."""
        try:
            self.player_list.pop(self.id_2_player[user_id].order)
        except KeyError:
            await self.broadcast(f"玩家 {user_id} 不存在于房间内")
            return
        for i in self.player_list[self.id_2_player[user_id].order :]:
            i.order -= 1
        del self.id_2_player[user_id]

    async def add_character(self, character_list: list[str]) -> None:
        """Enable roles by their alias text (e.g. '狼', 'seer')."""
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
        """Disable roles by their alias text."""
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
        """Change room settings (reserved for future use)."""
        self.settings[key] = value

    async def start_game(self) -> None:
        """Assign roles and enter the first night."""
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
        """Return a player by 1-based seat number."""
        if seat < 1 or seat > len(self.player_list):
            return None
        return self.player_list[seat - 1]

    def alive_players(self) -> list[Player]:
        """Return alive players in seat order."""
        return [p for p in self.player_list if p.alive]

    def alive_user_ids(self) -> set[str]:
        """Return alive player user_ids."""
        return {p.user_id for p in self.alive_players()}

    def alive_role_user_ids(self, role_id: str) -> set[str]:
        """Return alive user_ids of a given role_id."""
        return {
            p.user_id
            for p in self.player_list
            if p.alive and p.role and p.role.role_id == role_id
        }

    async def start_night(self) -> None:
        """Enter night phase and trigger role notifications."""
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
        """Try to lock the wolf kill decision.

        Rules (minimal):
        - If a target gets strict majority (> half of alive wolves): lock that kill immediately.
        - Otherwise, once all wolves have responded (voted or skipped): lock "no kill".
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
        """Record a wolf's kill vote for the current night."""
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
        """Notify alive witches of the current locked wolf target (for antidote choice)."""
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
        """Guard chooses a player to protect for this night."""
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
        """Witch uses antidote to cancel the wolf kill for this night."""
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
        """Witch poisons a player (additional night death)."""
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
        """Return seer check result text (wolf vs good) for a seat."""
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
        """Mark a player dead and trigger person_killed event."""
        if not player.alive:
            return
        player.alive = False
        await self.post_to_player(player.user_id, f"你已死亡 ({reason}) 。")
        await self.events_system.event_person_killed.active(
            self, player.user_id, [reason]
        )

    def check_winner(self) -> str | None:
        """Return 'good' or 'wolf' if a camp has won, otherwise None."""
        alive = self.alive_players()
        wolves = [p for p in alive if p.role and p.role.camp == "wolf"]
        goods = [p for p in alive if not (p.role and p.role.camp == "wolf")]
        if not wolves:
            return "good"
        if len(wolves) >= len(goods):
            return "wolf"
        return None

    async def resolve_night(self) -> None:
        """Resolve night actions and enter day speech."""
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
        """Start day speech phase.

        Speech order is seat order. Every other day the order is reversed.
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
        """Return current speaker user_id in day speech phase."""
        if self.state != "day":
            return None
        if self.day_speech_index < 0 or self.day_speech_index >= len(
            self.day_speech_order_user_ids
        ):
            return None
        return self.day_speech_order_user_ids[self.day_speech_index]

    async def end_speech_turn(self, user_id: str) -> tuple[bool, str]:
        """Advance speech to next speaker (only current speaker can call)."""
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
        """Enter vote phase and prompt players to vote."""
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
        """Cast/overwrite a vote for an alive target in vote phase."""
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
        """Skip the current required action (role action / speech / vote)."""
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
        """Resolve exile vote and start next night (or end game)."""
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
        """Advance state machine if all required actions for current phase are done."""
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
