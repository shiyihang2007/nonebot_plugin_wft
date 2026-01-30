from character_base import CharacterBase
from room import Room


class CharacterPerson(CharacterBase):
    aliases = ["person", "人", "民"]

    def __init__(self, room: Room) -> None:
        pass
