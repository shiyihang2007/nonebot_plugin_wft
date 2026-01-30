from utils import get_module_in_directory, get_classes_in_module
from player import Player

from character_base import CharacterBase
from event_system import EventSystem


character_modules = get_module_in_directory("nonebot_plugin_wft.game", "characters")
character_classes: list[type[CharacterBase]] = []
for module in character_modules:
    character_classes.extend(get_classes_in_module(module))


class Room:
    def __init__(
        self, group_id: str, func_send_group_message, func_send_private_message
    ) -> None:
        self.group_id: str = group_id
        self.func_send_group_message = func_send_group_message
        self.func_send_private_message = func_send_private_message
        self.player_list: list[Player] = []
        self.id_2_player: dict[str, Player] = {}
        self.events_system: EventSystem = EventSystem()
        self.character_enabled: dict[type[CharacterBase], int] = {}
        self.settings: dict[str, int | str | bool] = {}

    async def broadcast(self, message: str):
        await self.func_send_group_message(group_id=self.group_id, message=message)

    async def post_to_player(self, user_id: str, message: str):
        await self.func_send_private_message(user_id=user_id, message=message)

    async def add_player(self, user_id: str):
        if user_id in self.id_2_player:
            await self.broadcast(f"玩家 {user_id} 已在房间内")
            return
        self.id_2_player[user_id] = Player(user_id, len(self.player_list))
        self.player_list.append(self.id_2_player[user_id])

    async def remove_player(self, user_id: str):
        try:
            self.player_list.pop(self.id_2_player[user_id].order)
        except KeyError:
            await self.broadcast(f"玩家 {user_id} 不存在于房间内")
            return
        for i in self.player_list[self.id_2_player[user_id].order :]:
            i.order -= 1
        del self.id_2_player[user_id]

    async def add_character(self, character_list: list[str]):
        added_characters: list[str] = []
        for i in character_list:
            for j in character_classes:
                if i in j.aliases:
                    if j not in self.character_enabled:
                        self.character_enabled[j] = 0
                    self.character_enabled[j] += 1
                    added_characters.append(i)
        await self.broadcast(
            f"添加了角色: {', '.join(added_characters)}"
            if added_characters
            else "没有添加任何角色"
        )

    async def remove_character(self, character_list: list[str]):
        removed_characters: list[str] = []
        for i in character_list:
            for j in character_classes:
                if i in j.aliases:
                    if j in self.character_enabled:
                        self.character_enabled[j] -= 1
                        if self.character_enabled[j] <= 0:
                            del self.character_enabled[j]
                        removed_characters.append(i)
        await self.broadcast(
            f"移除了角色: {', '.join(removed_characters)}"
            if removed_characters
            else "没有移除任何角色"
        )

    def change_setting(self, key: str, value: int | str | bool):
        self.settings[key] = value

    async def start_game(self):
        pass
