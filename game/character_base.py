"""游戏循环使用的角色基类实现。

角色以类的形式实现，位于 `game/character_*.py` 中。游戏开始时会为每个玩家创建一个
角色实例，并将其绑定方法注册为房间 `EventSystem` 的监听器。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Any

if TYPE_CHECKING:
    from .room import Room
    from .player import Player


class CharacterBase:
    """角色基类（每名玩家对应一个实例）。"""

    role_id: ClassVar[str] = "base"
    name: ClassVar[str] = "未知"
    camp: ClassVar[str] = "neutral"  # "good" / "wolf" / "neutral"
    aliases: ClassVar[list[str]] = []  # 角色别名列表

    def __init__(self, room: Room, player: Player) -> None:
        """将角色绑定到玩家，并注册通用事件监听器。"""
        self.room = room
        self.player = player

        room.events_system.event_person_killed.add_listener(
            self.on_person_killed_update, priority=-10
        )

    @property
    def user_id(self) -> str:
        """该角色对应玩家的 OneBot user_id（QQ，内部以 str 存储）。"""
        return self.player.user_id

    @property
    def alive(self) -> bool:
        """玩家是否存活。"""
        return self.player.alive

    async def send_private(self, message: str) -> None:
        """给角色所属玩家发送私聊消息。"""
        await self.room.post_to_player(self.user_id, message)

    async def on_person_killed_update(
        self, room: Any, user_id: str | None, args: list[str]
    ) -> None:
        """有人死亡：
        - `user_id` 为死者，
        - `args[0]` 携带死亡原因字符串，
        - `args[1]` 携带下一事件（用于在需要等待玩家操作时阻塞流程，例如猎人亡语）。

        此监听器判断死者是否为自身并更改自身状态
        """
        if user_id != self.user_id:
            return
        await self.send_private(f"你已死亡，死因：{args[0]}")
        self.player.alive = False
