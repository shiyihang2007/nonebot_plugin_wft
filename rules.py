# 主要流程
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, Message
from src.plugins.nonebot_plugin_wft.states import (
    ActiveGroup,
    ActiveUsers,
    RoleCnt,
    RoleConfig,
    NowState,
    UserId2Role,
    Num2UserId,
    DeathList,
)
from src.plugins.nonebot_plugin_wft.units import (
    type2RoleStr,
    randomMode,
    role,
)
from src.plugins.nonebot_plugin_wft import botio

"""
0  wfInit
1  wfJoin
2  wfConfig
3  wfStart -> 4
4  wfSendRole -> 5
5  wfGoNight -> 6
6  wfSendSkill
7  wfSkillProc -> 6 / 8
8  wfSendDeath (11) -> 9
9  wfDiscuss -> 9 / 10
10 wfVote (11)
11 wfCheckOver -> 12
12 wfEnd
"""


# 创建
async def wfInit(bot: Bot, event: MessageEvent, arg: Message) -> str:
    """
    创建房间

    参数:
    - `bot: Bot` - 波特
    - `event: MessageEvent` - 事件
    - `arg: Message` - 命令参数
    """
    global ActiveGroup
    global RoleCnt
    global RoleConfig
    if event.message_type != "group":
        return "请在专用群聊使用"
    groupId: str = event.get_session_id().split("_")[1]
    if ActiveGroup == groupId:
        return "该群已有游戏房间"
    if ActiveGroup != "":
        return "已有游戏房间不在该群中"
    ActiveGroup = groupId
    RoleCnt = [0, 0, 0]
    for i in range(11):
        RoleConfig[i] = 0
    return "游戏房间初始化成功\n" + await wfConfig(bot, event, arg)


roleAlias: dict[str, int] = {
    "0": 0,
    "平民": 0,
    "好人": 0,
    "1": 1,
    "狼": 1,
    "狼人": 1,
    "2": 2,
    "预": 2,
    "预言": 2,
    "预言家": 2,
    "3": 3,
    "女巫": 3,
    "4": 4,
    "守": 4,
    "守卫": 4,
    "5": 5,
    "骑": 5,
    "骑士": 5,
    "6": 6,
    "猎": 6,
    "猎人": 6,
    "7": 7,
    "王": 7,
    "狼王": 7,
    "8": 8,
    "白狼": 8,
    "白狼王": 8,
    "9": 9,
    "隐": 9,
    "隐狼": 9,
    "10": 10,
    "白痴": 10,
    "傻瓜": 10,
}


# 自定义
async def wfConfig(bot: Bot, event: MessageEvent, arg: Message) -> str:
    """
    自定义房间

    参数:
    - `bot: Bot` - 波特
    - `event: MessageEvent` - 事件
    - `arg: Message` - 命令参数
    """
    global RoleCnt
    global RoleConfig
    if event.message_type != "group":
        return "请在专用群聊使用"
    groupId: str = event.get_session_id().split("_")[1]
    if ActiveGroup == "":
        return "游戏房间不存在,请先创建游戏"
    if ActiveGroup != groupId:
        return "游戏房间不在该群中"
    if NowState != 0:
        return "游戏正在进行中,请稍后再试"
    res: str = "回传信息:"
    args: list[str] = str(arg).split(" ")
    for nowConfig in args:
        configPair: list[str] = nowConfig.split(":")
        if len(configPair) < 2:
            res = (
                res
                + f"\n参数 '{nowConfig}'(eg {configPair}) 不合法"
                + f"(期望长度 >=2, 实际长度 {len(configPair)}), \n"
                + "可用参数 '种类:数量' '启用:职业[:数量]' '禁用:职业' '随机' ('[]'内为可选参数)"
            )
        try:
            if (
                configPair[0] == "人"
                or configPair[0] == "好人"
                or configPair[0] == "平民"
                or configPair[0] == "nb"
                or configPair[0] == "people"
                or configPair[0] == "goodman"
            ):
                RoleCnt[0] = int(configPair[1])
                res = res + f"\n已将 平民 数量设为 {configPair[1]}"
            elif (
                configPair[0] == "狼"
                or configPair[0] == "狼人"
                or configPair[0] == "wf"
                or configPair[0] == "wolf"
                or configPair[0] == "wolfman"
            ):
                RoleCnt[1] = int(configPair[1])
                res = res + f"\n已将 狼人 数量设为 {configPair[1]}"
            elif (
                configPair[0] == "神"
                or configPair[0] == "神职"
                or configPair[0] == "sp"
                or configPair[0] == "god"
                or configPair[0] == "super"
                or configPair[0] == "godman"
            ):
                RoleCnt[2] = int(configPair[1])
                res = res + f"\n已将 神职 数量设为 {configPair[1]}"
            elif (
                configPair[0] == "禁"
                or configPair[0] == "禁用"
                or configPair[0] == "disable"
                or configPair[0] == "turnoff"
            ):
                RoleConfig.pop(roleAlias[configPair[1]])
                res = res + f"\n已禁用 {type2RoleStr[roleAlias[configPair[1]]]} "
            elif (
                configPair[0] == "启"
                or configPair[0] == "启用"
                or configPair[0] == "enable"
                or configPair[0] == "turnon"
            ):
                if len(configPair) == 3:
                    RoleConfig[roleAlias[configPair[1]]] = int(configPair[2])
                    res = (
                        res
                        + f"\n已将 {type2RoleStr[roleAlias[configPair[1]]]} 数量设为 {int(configPair[2])}"
                    )
                else:
                    RoleConfig[roleAlias[configPair[1]]] = 1
                    res = res + f"\n已将 {type2RoleStr[roleAlias[configPair[1]]]} 数量设为 1"
            elif (
                configPair[0] == "随"
                or configPair[0] == "随机"
                or configPair[0] == "rand"
                or configPair[0] == "random"
            ):
                RoleCnt = [0, 0, 0]
        except IndexError:
            res = res + f"\n参数 '{nowConfig}'(eg {configPair}) 不合法"
            # 可用参数 '种类:数量' '启用:职业[:数量]' '禁用:职业' '随机' ('[]'内为可选参数)
    return res


async def wfJoin(bot: Bot, event: MessageEvent, arg: Message) -> str:
    global ActiveUsers
    if event.message_type != "group":
        return "请在专用群聊使用"
    groupId: str = event.get_session_id().split("_")[1]
    if ActiveGroup == "":
        return "游戏房间不存在,请先创建游戏"
    if ActiveGroup != groupId:
        return "游戏房间不在该群中"
    if NowState != 0:
        return "游戏正在进行中,请稍后再试"
    user_id: str = event.get_user_id()
    res: str = ""
    if user_id in ActiveUsers:
        res = f"{user_id} 已经在房间中"
        return res
    ActiveUsers.append(user_id)
    res = f"{user_id} 加入了房间\n当前人数 {len(ActiveUsers)}"
    return res


# 分配角色 & 开始
async def wfStart(bot: Bot, event: MessageEvent, arg: Message) -> None:
    global RoleCnt
    global RoleConfig
    global UserId2Role
    global NowState
    global Num2UserId
    if event.message_type != "group":
        res = "请在专用群聊使用"
        await bot.send(event=event, message=res, at_sender=True)
    groupId: str = event.get_session_id().split("_")[1]
    if ActiveGroup == "":
        res = "游戏房间不存在,请先创建游戏"
        await bot.send(event=event, message=res, at_sender=True)
    if ActiveGroup != groupId:
        res = "游戏房间不在该群中"
        await bot.send(event=event, message=res, at_sender=True)
    if NowState != 0:
        res = "游戏正在进行中,请稍后再试"
        await bot.send(event=event, message=res, at_sender=True)
    # if len(ActiveUsers) < 4:
    #     return f"参加人数太少了! ({len(ActiveUsers)}/4)"
    res: str = "--开始游戏--"
    # res = res + f"\n群聊: {ActiveGroup}"
    # res = res + f"\n玩家: {ActiveUsers}"
    if RoleCnt == [0, 0, 0]:
        res += "\n随机分配角色"
        gameMode: tuple[list[int], list[int]] = randomMode(len(ActiveUsers))
        RoleCnt = gameMode[0]
        cnt: int = len(ActiveUsers)
        rcnt: int = 1
        for i in gameMode[1]:
            RoleConfig[i] = cnt // rcnt
            cnt = cnt - cnt // rcnt
            rcnt = rcnt + 1
        res += f"\n角色配置为 {RoleCnt} | {RoleConfig}"
    if RoleCnt[0] != 0 and 0 not in RoleConfig:
        res += f"\n角色配置 {RoleConfig} 中不存在 平民(eg. 0) 职业, 已自动添加"
        RoleConfig[0] = RoleCnt[0]
    if RoleCnt[1] <= 0:
        res += f"\n角色配置 {RoleCnt} 不合法, 狼人数量必须为正整数!"
        await bot.send(event=event, message=res)
    if RoleConfig[1] + RoleConfig[7] + RoleConfig[8] != RoleCnt[1]:
        res += f"\n角色配置 {RoleCnt} 与 {RoleConfig} 中 狼人(eg. 1狼 7狼王 8白狼) 数量不符, 已自动更改"
        RoleConfig[1] = RoleCnt[1] - (RoleConfig[7] + RoleConfig[8])
        if RoleConfig[1] < 0:
            RoleConfig[7] += RoleConfig[1]
            RoleConfig[1] = 0
        if RoleConfig[7] < 0:
            RoleConfig[8] += RoleConfig[7]
            RoleConfig[7] = 0
        if RoleConfig[8] < 0:
            res += "\n自动更改失败, 狼人数量不能为负数!"
            await bot.send(event=event, message=res)
    if RoleCnt[0] + RoleCnt[1] + RoleCnt[2] != len(ActiveUsers):
        res += f"\n角色配置 {RoleCnt} 不适用于 {len(ActiveUsers)}人局"
        res += "\n请重新配置后再试"
        await bot.send(event=event, message=res)
    NowState = 1
    userList: list[str] = ActiveUsers
    nowUser: int = 0
    for nowRole in RoleConfig:
        num: int = RoleConfig[nowRole]
        for i in range(num):
            UserId2Role[userList[nowUser]] = role(nowRole)
            nowUser = nowUser + 1
            Num2UserId[nowUser] = userList[nowUser - 1]
            await botio.setGroupUserName(
                bot, ActiveGroup, userList[nowUser - 1], str(nowUser)
            )
    await bot.send(event=event, message=res)
    await wfSendRole(bot)
    await wfGoNight(bot)


# 发送角色
async def wfSendRole(bot: Bot) -> None:
    res: str = "--人员名单--"
    for i in range(1, len(Num2UserId) + 1):
        user: str = Num2UserId[i]
        await botio.privateSend(bot, user, Message(UserId2Role[user].getSkill()))
        res = res + f"\n  {user} | {i}号 -> [CQ:at,qq={str(int(user))}]"
    await botio.groupSend(bot, ActiveGroup, Message(res))


# 进入夜晚
async def wfGoNight(bot: Bot) -> None:
    global NowState
    NowState = 2
    await wfNextNightSkill(bot)


# 技能处理
nightSkillProcessList: list[int] = [4, 1, 3, 2]
nowNightSkillProcess: int = 0
nowNightSkillProcessCnt: int = 0
nowNightSkillDoCnt: int = 0


# 夜晚处理
# 下一个技能 / 转到天亮
async def wfNextNightSkill(bot: Bot) -> None:
    global nowNightSkillProcess
    global nowNightSkillProcessCnt
    global nowNightSkillDoCnt
    global NowState
    if nowNightSkillProcessCnt == len(nightSkillProcessList):
        # 天亮
        NowState = 3
        await wfSendDeath(bot)
        return
    nowNightSkillProcess = nightSkillProcessList[nowNightSkillProcessCnt]
    nowNightSkillProcessCnt = nowNightSkillProcessCnt + 1
    nowNightSkillDoCnt = 0
    await wfSendSkill(bot, nowNightSkillProcess)


# 发送技能
async def wfSendSkill(bot: Bot, nowRole: int) -> None:
    global nowNightSkillDoCnt
    if nowNightSkillDoCnt >= RoleConfig[nowRole]:
        await botio.groupSend(
            bot, ActiveGroup, Message(f"跳过了 {type2RoleStr[nowRole]} 的回合")
        )
        await wfNextNightSkill(bot)
        return
    nowNightSkillDoCnt = nowNightSkillDoCnt + 1
    await botio.groupSend(bot, ActiveGroup, Message(f"现在是 {type2RoleStr[nowRole]} 的回合"))
    for user in ActiveUsers:
        if UserId2Role[user].type == nowRole:
            await botio.privateSend(
                bot, user, Message(UserId2Role[user].getSkillHint())
            )


# 处理技能
async def wfNightSkillProc(bot: Bot, event: MessageEvent, arg: Message) -> None:
    if event.message_type != "private":
        await bot.send(event=event, message="请私聊 bot 使用!", at_sender=True)
        return
    if ActiveGroup == "":
        await bot.send(event=event, message="游戏房间不存在,请先创建游戏", at_sender=True)
        return
    if NowState != 2:
        await bot.send(event=event, message="当前不是夜晚哦")
        return
    # TODO 处理技能
    userId = event.get_user_id()
    userRole = UserId2Role[userId]
    args = str(arg).split()
    if userRole.type != nowNightSkillProcess:
        await bot.send(event=event, message="现在不是你的回合!")
    if userRole.type == 0:
        await bot.send(event=event, message="平民没有技能!")
    elif userRole.type == 1:
        if len(args) <= 0:
            await bot.send(event=event, message="你要刀谁?")
            return
        userIdToNum: dict[str, int] = {}
        userIdToNum.fromkeys(Num2UserId.items(), Num2UserId.keys())
        res: str = "你刀了:"
        for skillTo in args:
            if len(skillTo) < 5:
                # 使用编号
                skillToId = int(skillTo)
            else:
                skillToId = userIdToNum[str(int(skillTo))]
            DeathList.append(skillToId)
            res = res + f"\n  {Num2UserId[skillToId]} : {skillToId}号"
        await bot.send(event=event, message=res)
    elif userRole.type == 2:
        if len(args) <= 0:
            await bot.send(event=event, message="你要查谁?")
            return
    elif userRole.type == 3:
        pass
    elif userRole.type == 4:
        pass
    elif userRole.type == 5:
        pass
    elif userRole.type == 6:
        pass
    await wfNextNightSkill(bot)


# 发送死亡信息
async def wfSendDeath(bot: Bot) -> None:
    await botio.groupSend(
        bot,
        ActiveGroup,
        Message(str(f"昨晚有 {len(DeathList)} 个人死亡" if len(DeathList) > 0 else "昨晚是平安夜")),
    )
    if len(DeathList) > 0:
        res = "--死亡名单--"
        for i in DeathList:
            res = res + f"\n  {Num2UserId[i]} : {i}号 -> [CQ:at,qq={Num2UserId[i]}] 死了"
        await botio.groupSend(bot, ActiveGroup, Message(res))
        await wfCheckOver()


# 轮流发言
async def wfDiscuss(bot: Bot) -> None:
    pass


# 投票
async def wfVote(bot: Bot, event: MessageEvent, arg: Message):
    pass


# 结束判定
async def wfCheckOver():
    pass


# 结算
async def wfEnd():
    pass


# 强制结束
async def wfGiveUp(bot: Bot, event: MessageEvent, arg: Message) -> str:
    """
    结束游戏

    参数:
    - `bot: Bot` - 波特
    - `event: MessageEvent` - 事件
    - `arg: Message` - 命令参数
    """
    global ActiveGroup
    global ActiveUsers
    global NowState
    global RoleCnt
    global RoleConfig
    global UserId2Role
    global Num2UserId
    if ActiveGroup == "":
        return "当前没有正在进行的游戏!"
    res: str = f"游戏 {ActiveGroup} 先前状态 {NowState} 已结束!"
    ActiveUsers = []
    ActiveGroup = ""
    RoleCnt = []
    RoleConfig = {}
    UserId2Role = {}
    Num2UserId = {}
    NowState = 0
    return res
