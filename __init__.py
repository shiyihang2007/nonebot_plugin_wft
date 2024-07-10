# 命令处理
from game import Game
from botio import BotIO
from . import roles

from nonebot.adapters.onebot.v11 import Bot, Message, GroupMessageEvent
from nonebot import (
    CommandGroup,
)
from nonebot.params import CommandArg
from nonebot.rule import to_me
from nonebot.log import logger

# require("nonebot_plugin_datastore")
# from nonebot_plugin_datastore import PluginData


def get_classes_in_module(module: object):
    """动态编程黑魔法, 用来获取模块中的所有类"""
    classes = []
    for name in dir(module):
        member = getattr(module, name)
        if isinstance(member, type):
            classes.append(member)
    return classes


commandPrefix = CommandGroup("wft")

commandInit = commandPrefix.command("init", aliases={"创建", "开房", "初始化"})
commandEnd = commandPrefix.command("end", aliases={"结束", "中止"}, rule=to_me())

commandJoin = commandPrefix.command("join", aliases={"加入", "加", "进入", "进"})
commandExit = commandPrefix.command("exit", aliases={"退出", "退", "离开", "离"})
commandAddrole = commandPrefix.command("addrole", aliases={"添角色", "添"})
commandRmrole = commandPrefix.command("rmrole", aliases={"删角色", "删"})
commandShowroles = commandPrefix.command("showroles", aliases={"显示角色", "显"})
commandAutoroles = commandPrefix.command("autoroles", aliases={"自动角色", "自动"})
commandStart = commandPrefix.command("start", aliases={"开始", "启动"})

commandSkill = commandPrefix.command(
    "skill", aliases={"技能", "救", "刀", "查", "救", "毒"}
)
commandSkill = commandPrefix.command("skip", aliases={"跳过", "过", "不使用技能"})


games: dict[str, Game] = {}


@commandInit.handle()
async def _(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    global games, io
    if not io:
        io = BotIO(bot)
    groupId: str = str(event.group_id)
    if games[groupId]:
        await commandInit.finish("请先结束上一局游戏. ")
    games[groupId] = Game(groupId)
    await commandInit.finish("游戏已创建")


@commandEnd.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg()):
    global games
    groupId: str = str(event.group_id)
    if not games[groupId]:
        await commandEnd.finish("没有正在进行的游戏. ")
    games[groupId].endsUp(io)
    await commandEnd.finish("游戏已结束")


@commandJoin.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg()):
    global games
    groupId: str = str(event.group_id)
    playerId: str = event.get_user_id()
    games[groupId].addPlayer(playerId)
    await commandJoin.finish(f"[CQ:at,qq={playerId}] 已加入游戏")


@commandExit.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg()):
    global games
    groupId: str = str(event.group_id)
    playerId: str = event.get_user_id()
    games[groupId].removePlayer(playerId)
    await commandExit.finish(f"[CQ:at,qq={playerId}] 已离开游戏")


@commandAddrole.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg()):
    global games
    groupId: str = str(event.group_id)
    roleList = args.extract_plain_text().split(" ")
    roleClasses: list[roles.RoleBase] = get_classes_in_module(roles)
    for roleName in roleList:
        tps: list[roles.RoleBase] = [
            x() for x in roleClasses if roleName in x.typeAlias
        ]
        if len(tps) > 1:
            logger.warning(
                f"Other items with the same name ({roleName}) are ignored. e.g.{tps[1:]}"
            )
        games[groupId].addRole(tps[0])
        await commandAddrole.send(f"已添加角色 {tps[0].getType()}")


@commandRmrole.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg()):
    global games
    groupId: str = str(event.group_id)
    roleList = args.extract_plain_text().split(" ")
    for roleName in roleList:
        if roleName is int:
            pos = roleName
        else:
            tps = [x() for x in games[groupId].roleList if roleName in x.typeAlias]
            if len(tps) > 1:
                logger.warning(
                    f"Other items with the same name ({roleName}) are ignored. e.g.{tps[1:]}"
                )
        tp = games[groupId].roleList[pos].getType()
        games[groupId].removeRole(pos)
        await commandAddrole.send(f"已删除角色 {tp}")


@commandShowroles.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg()):
    global games
    groupId: str = str(event.group_id)
    await commandShowroles.send(
        f"角色列表: {[x.getType() for x in games[groupId].roleList]}"
    )


@commandAutoroles.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg()):
    global games
    groupId: str = str(event.group_id)
    if error := games[groupId].useDefaultRoleLists():
        await commandAutoroles.finish(error)


@commandStart.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg()):
    global games
    groupId: str = str(event.group_id)
    if error := games[groupId].start(io):
        await commandStart.finish(error)
