"""Base role implementation used by the game loop.

Roles are implemented as classes living in `game/character_*.py`. A role instance is created
for each player on game start and registers its bound methods as listeners on the room's
EventSystem.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Any

if TYPE_CHECKING:
    from .room import Room
    from .player import Player


class CharacterBase:
    """角色基类 (one instance per player)."""

    role_id: ClassVar[str] = "base"
    name: ClassVar[str] = "未知"
    camp: ClassVar[str] = "neutral"  # "good" / "wolf" / "neutral"
    aliases: ClassVar[list[str]] = []  # 角色别名列表

    def __init__(self, room: Room, player: Player) -> None:
        """Attach role to a player and register default event listeners."""
        self.room = room
        self.player = player

        room.events_system.event_night_start.listeners.append(self.on_night_start)
        room.events_system.event_day_start.listeners.append(self.on_day_start)
        room.events_system.event_vote_start.listeners.append(self.on_vote_start)
        room.events_system.event_use_skill.listeners.append(self.on_use_skill)
        room.events_system.event_person_killed.listeners.append(self.on_person_killed)

    @property
    def user_id(self) -> str:
        """OneBot user_id (QQ) for this role's player (stored as str)."""
        return self.player.user_id

    @property
    def alive(self) -> bool:
        """Whether the player is alive."""
        return self.player.alive

    async def send_private(self, message: str) -> None:
        """Send a private message to the role owner."""
        await self.room.post_to_player(self.user_id, message)

    async def on_night_start(self, room: Any, user_id: str | None, args: list[str]) -> None:
        """Night phase begins (roles typically prompt their actions here)."""
        return

    async def on_day_start(self, room: Any, user_id: str | None, args: list[str]) -> None:
        """Day phase begins (after night resolution)."""
        return

    async def on_vote_start(self, room: Any, user_id: str | None, args: list[str]) -> None:
        """Vote phase begins."""
        return

    async def on_use_skill(self, room: Any, user_id: str | None, args: list[str]) -> None:
        """A player issued `/wft skill ...`."""
        return

    async def on_person_killed(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        """Someone died. `user_id` is the victim, `args` carries reason strings."""
        return
