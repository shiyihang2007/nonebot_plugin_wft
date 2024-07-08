import random

type2RoleStr: dict[int, str] = {
    0: "平民",
    1: "狼人",
    2: "预言家",
    3: "女巫",
    4: "守卫",
    5: "骑士",
    6: "猎人",
    7: "狼王",
    8: "白狼王",
    9: "隐狼",
    10: "白痴",
}
"""
角色类型 -> 名称
"""
type2RoleSkill: dict[int, str] = {
    0: """【角色】：平民
【阵营】：好人阵营，平民
【能力】：无特殊技能，一觉睡到天亮。
【目标】：分析其他玩家发言，认真地投出每一票，直到驱逐所有狼人。""",
    1: """【角色】：狼人
【阵营】：狼人阵营
【能力】：每天夜里可以杀死一个人。
【目标】：白天装作好人混淆视听，夜晚袭击村民，霸占村庄。""",
    2: """【角色】：预言家
【阵营】：好人阵营，神职
【能力】：每天晚上可以查验一名玩家的身份是好人还是狼人。
【目标】：利用自己的能力带领大家找出、驱逐所有狼人。
【使用】：/查 号数""",
    3: """【角色】：女巫
【阵营】：好人阵营，神职
【能力】：女巫拥有两瓶药，解药可以救活一名当晚被狼人杀害的玩家，毒药可以毒杀一名玩家，女巫每天晚上最多使用一瓶药，女巫不可自救。
【目标】：善用毒药和解药，驱逐全部狼人出局。
【使用】：/毒 号数 /救 号数""",
    4: """【角色】：守卫
【阵营】：好人阵营，神职
【能力】：每晚可以守护一名玩家，包括自己，但不能连续两晚守护同一名玩家。被守卫守护的玩家当晚不会被狼人杀害。
【目标】：守护关键好人，驱逐狼人获胜。
【使用】：/守护 号数""",
    5: """【角色】：骑士
【阵营】：好人阵营，神职
【能力】：骑士可以在白天发言结束，放逐投票之前，翻牌决斗场上除自己以外的任意一位玩家。如果被决斗的玩家是狼人，则该狼人死亡并立即进入黑夜；如果被决斗的玩家是好人，则骑士死亡，并继续进行白天原本的发言流程。
【目标】：在确定狼人的情况下，发动技能杀死狼人。
【使用】：/决斗 号数""",
    6: """【角色】：猎人
【阵营】：好人阵营，神职
【能力】：当且仅当猎人被狼人杀害或被投票放逐时，猎人可以亮出自己的身份牌并指定枪杀一名玩家，被女巫毒杀则无法发动技能。
【目标】：一命换一命，驱逐全部狼人出局。
【使用】：/杀 号数""",
    7: """【角色】：狼王
【阵营】：狼人阵营
【能力】：属于狼人阵营，具有死后开枪技能。（殉情、自爆和被毒杀不能开枪）
【目标】：白天装作好人混淆视听，夜晚袭击村民，霸占村庄。""",
    8: """【角色】：白狼王
【阵营】：狼人阵营
【能力】：属于狼人阵营，白狼王可以在白天自爆的时候，选择带走一名玩家，非自爆出局不得发动技能。
【目标】：白天装作好人混淆视听，夜晚袭击村民，霸占村庄。
【使用】：/自爆 号数 (在白天任意时刻私聊使用)""",
    9: """【角色】：隐狼
【阵营】：狼人阵营
【能力】：隐狼属于狼人阵营，不能自爆，被预言家查验结果始终为好人。隐狼夜间知道其他那些玩家是狼人，但不能同其他狼人一起刀人，狼队友也不知道隐狼身份。当其他狼同伴全部出局后，进入狼坑，获得刀人技能。
【目标】：白天若被真预言家发金水且发言正常，可以基本坐实好人身份。
请遵守游戏规则,不与队友对话!""",
    10: """【角色】：白痴
【阵营】：好人阵营，神职
【能力】：白痴被投票出局，可以翻开自己的身份牌，免疫此次放逐，之后可以正常发言，但不能投票，狼人仍需要击杀他才能让他死亡。但若是白痴因非投票原因死亡，则无法发动技能，立即死亡。
【目标】：驱逐全部狼人出局。""",
}
"""
角色类型 -> 技能介绍
"""
type2RoleSkillHint: dict[int, str] = {
    0: "你没有技能可以使用",
    1: "(多个狼人共享技能,请跟同伴商量好再出手)请商量刀谁,不使用技能回复/不使用技能\neg:/刀 阿拉伯数字",
    2: "请考虑查谁,不使用技能回复/不使用技能\neg:/查 阿拉伯数字",
    3: "请考虑毒谁,不使用技能回复/不使用技能\neg:/毒 阿拉伯数字",
    4: "请选择守护号数,不使用技能回复/不使用技能\neg:/守护 阿拉伯数字",
    5: "你可以在白天任意时候使用技能一次,请考虑决斗谁\neg:/决斗 阿拉伯数字",
    6: "你已经死亡,请考虑枪谁,不使用技能回复/枪 0\neg:/枪 阿拉伯数字",
    7: "你已经死亡,请考虑杀谁,不使用回复/杀 0\neg:/杀 阿拉伯数字",
    8: "你可以在白天任意时候自爆,请考虑自爆谁\neg:/自爆 阿拉伯数字",
    9: "技能释放!请考虑刀谁,不使用技能回复/不使用技能\neg:/刀 阿拉伯数字",
    10: "你没有技能可以使用",
}
"""
角色类型 -> 技能提示
"""

deathReasons: list[str] = [
    "被刀了",
    "被票出了",
    "被毒死了",
    "被枪决了",
    "自爆了",
    "被自爆带走了",
    "殉情了",
]


class RoleBase:
    """
    角色基类
    """

    id: int
    name: str

    def __init__(self, type: int = 0) -> None:
        pass

    def getType(self) -> int:
        return -1

    def getBelong(self) -> str:
        return """第三阵营"""

    def getIntro(self) -> str:
        return """暂无介绍"""

    def onNight(self) -> str | None:
        return None

    def onDay(self) -> str | None:
        return None

    def onPeopleDeath(self, who: str) -> str | None:
        return None

    def onDeath(self) -> str | None:
        return None


class RolePerson(RoleBase):
    """
    【角色】：平民\n
    【阵营】：好人阵营，平民\n
    【能力】：无特殊技能，一觉睡到天亮。\n
    【目标】：分析其他玩家发言，认真地投出每一票，直到驱逐所有狼人。"""

    def getType(self) -> int:
        return 0

    def getBelong(self) -> str:
        return """好人阵营"""

    def getIntro(self) -> str:
        return """【角色】：平民
【阵营】：好人阵营，平民
【能力】：无特殊技能，一觉睡到天亮。
【目标】：分析其他玩家发言，认真地投出每一票，直到驱逐所有狼人。"""


class RoleWolf(RoleBase):
    """
    【角色】：狼人\n
    【阵营】：狼人阵营\n
    【能力】：每天夜里可以杀死一个人。\n
    【目标】：白天装作好人混淆视听，夜晚袭击村民，霸占村庄。"""

    def getType(self) -> int:
        return 1

    def getIntro(self) -> str:
        return """【角色】：狼人
【阵营】：狼人阵营
【能力】：每天夜里可以杀死一个人。
【目标】：白天装作好人混淆视听，夜晚袭击村民，霸占村庄。"""

    def onNight(self) -> str | None:
        return "(多个狼人共享技能,请跟同伴商量好再出手)请商量刀谁,不使用技能回复/不使用技能\neg:/刀 阿拉伯数字"


class RolePredicter(RolePerson):
    """【角色】：预言家\n
    【阵营】：好人阵营，神职\n
    【能力】：每天晚上可以查验一名玩家的身份是好人还是狼人。\n
    【目标】：利用自己的能力带领大家找出、驱逐所有狼人。\n
    【使用】：/查 号数"""

    def getType(self) -> int:
        return 2

    def getIntro(self) -> str:
        return """【角色】：预言家
【阵营】：好人阵营，神职
【能力】：每天晚上可以查验一名玩家的身份是好人还是狼人。
【目标】：利用自己的能力带领大家找出、驱逐所有狼人。
【使用】：/查 号数"""

    def onNight(self) -> str | None:
        return "请考虑查谁,不使用技能回复/不使用技能\neg:/查 阿拉伯数字"


class RoleWitch(RolePerson):
    """【角色】：女巫\n
    【阵营】：好人阵营，神职\n
    【能力】：女巫拥有两瓶药，解药可以救活一名当晚被狼人杀害的玩家，毒药可以毒杀一名玩家，女巫每天晚上最多使用一瓶药，女巫不可自救。\n
    【目标】：善用毒药和解药，驱逐全部狼人出局。\n
    【使用】：/毒 号数 /救 号数"""

    haveAntidote: bool = True
    havePoison: bool = True

    def getType(self) -> int:
        return 3

    def getIntro(self) -> str:
        return """【角色】：女巫
【阵营】：好人阵营，神职
【能力】：女巫拥有两瓶药，解药可以救活一名当晚被狼人杀害的玩家，毒药可以毒杀一名玩家，女巫每天晚上最多使用一瓶药，女巫不可自救。
【目标】：善用毒药和解药，驱逐全部狼人出局。
【使用】：/毒 号数 /救 号数"""

    def onNight(self) -> str | None:
        if self.havePoison:
            return "请考虑毒谁,不使用技能回复/不使用技能\neg:/毒 阿拉伯数字"
        return None

    def onPeopleDeath(self, who: str) -> str | None:
        if self.haveAntidote:
            if who == self.name:
                return "刚才 你 死了,但你不能自救.请回复/不使用技能"
            return f"刚才 {who} 死了,你要救吗?不使用技能回复/不使用技能\neg:/救"
        return None


class RoleGuard(RolePerson):
    """【角色】：守卫\n
    【阵营】：好人阵营，神职\n
    【能力】：每晚可以守护一名玩家，包括自己，但不能连续两晚守护同一名玩家。被守卫守护的玩家当晚不会被狼人杀害。\n
    【目标】：守护关键好人，驱逐狼人获胜。\n
    【使用】：/守护 号数"""

    def getType(self) -> int:
        return 4

    def getIntro(self) -> str:
        return """【角色】：守卫
【阵营】：好人阵营，神职
【能力】：每晚可以守护一名玩家，包括自己，但不能连续两晚守护同一名玩家。被守卫守护的玩家当晚不会被狼人杀害。
【目标】：守护关键好人，驱逐狼人获胜。
【使用】：/守护 号数"""

    def onNight(self) -> str | None:
        return "请选择守护号数,不使用技能回复/不使用技能\neg:/守护 阿拉伯数字"


class RoleKnight(RolePerson):
    """【角色】：骑士\n
    【阵营】：好人阵营，神职\n
    【能力】：骑士可以在白天发言结束，放逐投票之前，翻牌决斗场上除自己以外的任意一位玩家。如果被决斗的玩家是狼人，则该狼人死亡并立即进入黑夜；如果被决斗的玩家是好人，则骑士死亡，并继续进行白天原本的发言流程。\n
    【目标】：在确定狼人的情况下，发动技能杀死狼人。\n
    【使用】：/决斗 号数"""

    def getType(self) -> int:
        return 5

    def getIntro(self) -> str:
        return """【角色】：骑士
【阵营】：好人阵营，神职
【能力】：骑士可以在白天发言结束，放逐投票之前，翻牌决斗场上除自己以外的任意一位玩家。如果被决斗的玩家是狼人，则该狼人死亡并立即进入黑夜；如果被决斗的玩家是好人，则骑士死亡，并继续进行白天原本的发言流程。
【目标】：在确定狼人的情况下，发动技能杀死狼人。
【使用】：/决斗 号数"""

    def onDay(self) -> str | None:
        return "你可以在白天任意时候使用技能一次,请考虑决斗谁\neg:/决斗 阿拉伯数字"


class RoleHunter(RolePerson):
    """【角色】：猎人\n
    【阵营】：好人阵营，神职\n
    【能力】：当且仅当猎人被狼人杀害或被投票放逐时，猎人可以亮出自己的身份牌并指定枪杀一名玩家，其它情况则无法发动技能。\n
    【目标】：一命换一命，驱逐全部狼人出局。\n
    【使用】：/杀 号数"""

    def getType(self) -> int:
        return 6

    def getIntro(self) -> str:
        return """【角色】：猎人
【阵营】：好人阵营，神职
【能力】：当且仅当猎人被狼人杀害或被投票放逐时，猎人可以亮出自己的身份牌并指定枪杀一名玩家，其它情况则无法发动技能。
【目标】：一命换一命，驱逐全部狼人出局。
【使用】：/杀 号数"""

    def onDeath(self, reason: str) -> str | None:
        if reason in ["被刀了", "被票出了"]:
            return "你已经死亡,请考虑枪谁,不使用技能回复/枪 0\neg:/枪 阿拉伯数字"
        return None


class RoleBlackWolfKing(RoleWolf):
    """【角色】：黑狼王\n
    【阵营】：狼人阵营\n
    【能力】：属于狼人阵营，具有死后开枪技能。（殉情、自爆和被毒杀不能开枪）\n
    【目标】：白天装作好人混淆视听，夜晚袭击村民，霸占村庄。"""

    def getType(self) -> int:
        return 7

    def getIntro(self) -> str:
        return """【角色】：黑狼王
【阵营】：狼人阵营
【能力】：属于狼人阵营，具有死后开枪技能。（殉情、自爆和被毒杀不能开枪）
【目标】：白天装作好人混淆视听，夜晚袭击村民，霸占村庄。"""

    def onDeath(self, reason: str) -> str | None:
        if reason in ["被刀了", "被票出了"]:
            return "你已经死亡,请考虑杀谁,不使用回复/杀 0\neg:/杀 阿拉伯数字"
        return None


class RoleWhiteWolfKing(RoleWolf):
    """【角色】：白狼王\n
    【阵营】：狼人阵营\n
    【能力】：属于狼人阵营，白狼王可以在白天自爆的时候，选择带走一名玩家，非自爆出局不得发动技能。\n
    【目标】：白天装作好人混淆视听，夜晚袭击村民，霸占村庄。\n
    【使用】：/自爆 号数 (在白天任意时刻私聊使用)"""

    def getType(self) -> int:
        return 8

    def getIntro(self) -> str:
        return """【角色】：白狼王
【阵营】：狼人阵营
【能力】：属于狼人阵营，白狼王可以在白天自爆的时候，选择带走一名玩家，非自爆出局不得发动技能。
【目标】：白天装作好人混淆视听，夜晚袭击村民，霸占村庄。
【使用】：/自爆 号数 (在白天任意时刻私聊使用)"""

    def onDay(self) -> str | None:
        return "你可以在白天任意时候自爆,请考虑自爆谁\neg:/自爆 阿拉伯数字"


# unfinish
class RoleHiddenWolf(RoleWolf):
    """【角色】：隐狼\n
    【阵营】：狼人阵营\n
    【能力】：隐狼属于狼人阵营，不能自爆，被预言家查验结果始终为好人。隐狼夜间知道其他那些玩家是狼人，但不能同其他狼人一起刀人，狼队友也不知道隐狼身份。当其他狼同伴全部出局后，进入狼坑，获得刀人技能。\n
    【目标】：白天若被真预言家发金水且发言正常，可以基本坐实好人身份。\n
    请遵守游戏规则,不与队友对话!"""

    def getType(self) -> int:
        return 9

    def getIntro(self) -> str:
        return """【角色】：隐狼
【阵营】：狼人阵营
【能力】：隐狼属于狼人阵营，不能自爆，被预言家查验结果始终为好人。隐狼夜间知道其他那些玩家是狼人，但不能同其他狼人一起刀人，狼队友也不知道隐狼身份。当其他狼同伴全部出局后，进入狼坑，获得刀人技能。
【目标】：白天若被真预言家发金水且发言正常，可以基本坐实好人身份。
请遵守游戏规则,不与队友对话!"""


# unfinish
class RoleStupid(RolePerson):
    """【角色】：白痴\n
    【阵营】：好人阵营，神职\n
    【能力】：白痴被投票出局，可以翻开自己的身份牌，免疫此次放逐，之后可以正常发言，但不能投票，狼人仍需要击杀他才能让他死亡。但若是白痴因非投票原因死亡，则无法发动技能，立即死亡。\n
    【目标】：驱逐全部狼人出局。"""

    def getType(self) -> int:
        return 10

    def getIntro(self) -> str:
        return """【角色】：白痴
【阵营】：好人阵营，神职
【能力】：白痴被投票出局，可以翻开自己的身份牌，免疫此次放逐，之后可以正常发言，但不能投票，狼人仍需要击杀他才能让他死亡。但若是白痴因非投票原因死亡，则无法发动技能，立即死亡。
【目标】：驱逐全部狼人出局。"""


# 随机排列角色顺序
def randomRoleType(
    *typelist: int,
):
    reslist: list[int] = []
    for i in typelist:
        reslist.append(i)
    random.shuffle(reslist)
    return reslist


# 随机模式
def randomMode(playerCount: int) -> tuple[list[int], list[int]]:
    roleCnt: list[int] = [0, 0, 0]
    roleEnabled: list[int] = []
    if playerCount == 6:
        roleCnt = [2, 2, 2]
        if random.randint(0, 1) == 0:
            roleEnabled = [0, 1, 2, 3]
        else:
            roleEnabled = [0, 1, 2, 4]
    elif playerCount == 7:
        roleCnt = [4, 2, 1]
        roleEnabled = [0, 1, 2, 3, 4, 6, 8]
    elif playerCount == 8:
        roleCnt = [3, 3, 2]
        roleEnabled = [1, 0, 2, 4, 5]
    elif playerCount == 9:
        roleCnt = [3, 3, 3]
        roleEnabled = [1, 0, 2, 4, 3, 6]
    elif playerCount == 10 or playerCount == 11:
        m = random.randint(0, 2)
        if m == 0:
            roleCnt = [3, 3, playerCount - 6]
            roleEnabled = [1, 0, 2, 3, 6]
        elif m == 1:
            roleCnt = [4, 3, playerCount - 7]
            roleEnabled = [
                1,
                8,
                0,
                2,
                3,
                5,
                10,
            ]
        elif m == 2:
            roleCnt = [3, 4, playerCount - 7]
            roleEnabled = [1, 0, 2, 3, 5, 9]
    elif playerCount == 12:
        m = random.randint(0, 4)
        roleCnt = [4, 4, 4]
        if m == 0:
            roleEnabled = [
                1,
                0,
                2,
                3,
                6,
                randomRoleType(1, 10, 4)[0],
            ]
        elif m == 1:
            roleEnabled = [
                1,
                9,
                0,
                2,
                3,
                6,
            ]
        elif m == 2:
            roleEnabled = [
                1,
                8,
                0,
                2,
                3,
                randomRoleType(1, 5, 6)[0],
                4,
            ]
        elif m == 3:
            roleEnabled = [
                1,
                7,
                0,
                2,
                3,
                6,
                randomRoleType(1, 4)[0],
            ]

    return roleCnt, roleEnabled
