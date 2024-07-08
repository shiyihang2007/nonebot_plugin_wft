import random
from . import roles


class Game:
    groupId: str = ""

    playerList: list[str] = []
    roleList: list[roles.RoleBase] = []
    deathList: list[int] = []

    nowState: int = 0
    """
    - `0` - 准备阶段
    - `1` - 初始化阶段
    - `2` - 夜晚阶段
    - `3` - 白天阶段
    - `4` - 结算阶段
    """

    def __init__(self, group: str) -> None:
        self.groupId = group

    def addPlayer(self, player: str):
        self.playerList.append(player)

    def addRole(self, role):
        self.roleList.append(role)

    def removePlayer(self, pos):
        self.playerList.remove(self.playerList[pos])

    def removeRole(self, pos):
        self.roleList.remove(self.roleList[pos])

    @staticmethod
    def randomRoles(gameRoles: list[roles.RoleBase], players: list[str]) -> str | None:
        try:
            random.shuffle(players)
            random.shuffle(gameRoles)
            for i in range(len(gameRoles)):
                t = gameRoles[i]
                t.id = i
                t.name = players[i]
        except:
            return "Cannot Match Players & Roles"
