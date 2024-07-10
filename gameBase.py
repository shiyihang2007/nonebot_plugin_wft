"""游戏内部接口
狼人杀 中
玩家死亡 / 取消死亡 / 获取阵营
的接口定义
"""


class GameBase:

    def playerProtected(self, id: int):
        pass

    def playerKilled(self, id: int):
        pass

    def playerSaved(self, id: int):
        pass

    def playerPoisoned(self, id: int):
        pass

    def getDeadPlayer(self) -> str:
        pass

    def getPlayerBelong(self, id: int) -> str:
        pass
