"""Player model for a Room (seat order + alive state + assigned role)."""

from __future__ import annotations

from .character_base import CharacterBase


class Player:
    """A participant in a Room.

    `order` is 0-based seat index. The UI uses `seat` (1-based).
    """

    def __init__(self, user_id: str, order: int) -> None:
        self.role: CharacterBase | None = None
        self.user_id = user_id
        self.order = order
        self.alive: bool = True

    @property
    def seat(self) -> int:
        return self.order + 1
