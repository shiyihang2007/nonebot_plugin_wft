"""游戏内部接口
狼人杀 中
玩家死亡 / 取消死亡 / 获取阵营
的接口定义
"""


class GameBase:
    def name2id(self, name: str) -> int:
        raise NotImplementedError

    def id2name(self, uid: int) -> str:
        raise NotImplementedError

    def getGroupId(self) -> str:
        raise NotImplementedError

    def playerProtected(self, uid: int):
        raise NotImplementedError

    def playerKilled(self, uid: int):
        raise NotImplementedError

    def playerSaved(self, uid: int):
        raise NotImplementedError

    def playerPoisoned(self, uid: int):
        raise NotImplementedError

    def playerShot(self, uid: int):
        raise NotImplementedError

    def getDeadPlayer(self) -> str | None:
        raise NotImplementedError

    def getPlayerBelong(self, uid: int) -> str:
        raise NotImplementedError
