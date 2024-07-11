import random

from .gameBase import GameBase
from .roles import RoleBase
from .botio import BotIO


class Game(GameBase):
    groupId: str = ""

    playerList: list[str] = []
    roleList: list[RoleBase] = []
    deathList: list[int] = []

    killEdge: bool = False
    personSet: list[int] = [0]

    nowDays: int = 0

    lstDeath: list[str] = []
    roleActionList: list[int] = []

    i: int = 0
    votes: list[int] = []

    def __init__(self, group: str) -> None:
        self.groupId = group

        self.playerList = []
        self.roleList = []
        self.deathList = []
        self.killEdge = False
        self.personSet = [0]

        self.nowDays = 0

        self.lstDeath = []
        self.roleActionList = []

    # 设置用
    def addPlayer(self, player: str):
        self.playerList.append(player)

    def addRole(self, role: RoleBase):
        self.roleList.append(role)

    def removePlayer(self, pos):
        self.playerList.remove(self.playerList[pos])

    def removeRole(self, pos):
        self.roleList.remove(self.roleList[pos])

    def setGameMode(self, killEdge: bool = False):
        self.killEdge = killEdge

    def setPersonSet(self, personSet: list[int]):
        self.personSet = personSet

    def useDefaultRoleLists(self) -> str | None:
        self.roleList.clear()
        n: int = len(self.playerList)
        if n == 9:
            pass
        else:
            return "The number of people is illegal"

    # 启动!
    def randomRoles(self) -> str | None:
        try:
            random.shuffle(self.playerList)
            random.shuffle(self.roleList)
            for i in range(len(self.roleList)):
                self.roleList[i].id = i
                self.roleList[i].name = self.playerList[i]
        except:
            return "随机匹配失败了. 请检查人数和角色数是否匹配. "

    def start(self, io: BotIO) -> str | None:
        if error := self.randomRoles():
            return error
        self.roleActionList = range(len(self.roleList))
        self.roleActionList.sort(key=lambda x: self.roleList[x].getPriority())
        self.i = 0
        self.onNight(self)

    # 每天事务
    def onNight(self, io: BotIO) -> str | None:
        io.groupSend(self.groupId, "天黑请闭眼")
        for x in self.roleList:
            x.canUseSkill = False
        if error := self._nightActions(io):
            return error

    def _nightActions(self, io: BotIO) -> str | None:
        if self.i < len(self.roleList):
            if msg := self.roleList[self.roleActionList[self.i]].onNight():
                self.roleList[self.roleActionList[self.i]].canUseSkill = True
                io.privateSend(self.roleList[self.roleActionList[self.i]].name, msg)
            self.i += 1
        else:
            self.onDay(io)

    def onDay(self, io: BotIO) -> str | None:
        if len(self.lstDeath) > 0:
            deathMsg: str = ""
            for i in self.deathList:
                deathMsg += f"[CQ:at,qq={i}],"
            deathMsg = deathMsg.removesuffix(",")
            io.groupSend(
                self.groupId,
                f"天亮了, 昨晚 {deathMsg} 死了",
            )
        else:
            io.groupSend(
                self.groupId,
                "天亮了, 昨晚是平安夜",
            )
        if error := self.checkEnding(io):
            return error
        self.i = 0
        if error := self._giveSpeech(io):
            return error

    def checkEnding(self, io: BotIO) -> str | None:
        if msg := self._checkEnding():
            io.groupSend(self.groupId, msg)
            return msg

    def _giveSpeech(self, io: BotIO) -> str | None:
        io.groupSend(
            self.groupId,
            f"""有请 [CQ:at,qq={self.playerList[self.i if self.nowDays % 2 == 1 else len(self.playerList) - self.i + 1]}] 发言
              结束请发 过""",
        )
        self.i += 1

    def _vote(self, io: BotIO) -> str | None:
        self.votes = [0] * len(self.playerList)
        io.groupSend(
            self.groupId,
            """进入投票环节
            投票请发 投 谁
            弃票请投 -1""",
        )

    def _checkEnding(self) -> str | None:
        goods = [
            x.id for x in self.roleList if x.getBelong() == "好人阵营" and not x.isDeath
        ]
        persons = [
            x.id for x in self.roleList if x.getId() in self.personSet and not x.isDeath
        ]
        bads = [
            x.id for x in self.roleList if x.getBelong() == "狼人阵营" and not x.isDeath
        ]
        others = [
            x.id
            for x in self.roleList
            if x.getBelong() != "好人阵营"
            and x.getBelong() != "狼人阵营"
            and not x.isDeath
        ]
        if not goods and not bads and not others:
            return "无人生还"
        elif (self.killEdge and not persons and not others) or (
            not self.killEdge and not goods and not others
        ):
            return "狼人获胜"
        elif not bads and not others:
            return "好人获胜"
        elif others and not goods and not bads:
            return f"{[f"[CQ:at,qq={x}]" for x in others]} 获胜"

    def endsUp(self, io: BotIO) -> str | None:
        io.groupSend(
            self.groupId, f"{[x.id for x in self.roleList if not x.isDeath]} 生还"
        )
        msg: str = "角色列表:\n"
        for x in [f"[CQ:at,qq={x.id}]: {x.getType()}\n" for x in self.roleList]:
            msg += x
        io.groupSend(self.groupId, msg.removesuffix("\n"))
