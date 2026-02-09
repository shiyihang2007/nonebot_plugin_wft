"""`Room` 的玩家模型（座位顺序 / 存活状态 / 分配的角色）。"""

from __future__ import annotations

from .character_base import CharacterBase


class Player:
    """房间中的参与者。

    - `order`：0 基座位下标
    - `seat`：展示用的 1 基座位号
    """

    def __init__(self, user_id: str, order: int) -> None:
        self.role: CharacterBase | None = None
        self.user_id = user_id
        self.order = order
        self.alive: bool = True

    @property
    def seat(self) -> int:
        return self.order + 1
