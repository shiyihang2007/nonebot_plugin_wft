from character_base import CharacterBase


class Player:
    def __init__(self, user_id: str, order: int) -> None:
        self.role: CharacterBase | None = None
        self.user_id = user_id
        self.order = order
