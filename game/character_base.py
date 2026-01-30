from room import Room


class CharacterBase:
    """
    角色基类
    """

    aliases: list[str] = []  # 角色别名列表

    def __init__(self, room: Room) -> None:
        raise NotImplementedError
