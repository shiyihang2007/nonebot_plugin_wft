# 命令处理
from gc import enable
from click import group
from .game import Game
from .botio import BotIO
from . import roles

from nonebot.adapters.onebot.v11 import (
    Bot,
    Message,
    MessageEvent,
    GroupMessageEvent,
    PrivateMessageEvent,
)
from nonebot import (
    CommandGroup,
)
from nonebot.typing import T_State
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER
from nonebot.rule import Rule, to_me
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


ban_user: dict[str, set[str]] = dict()
enabled_groups: set[str] = set()


async def is_enabled(event: MessageEvent) -> bool:
    user_id: str = event.get_user_id()
    if isinstance(event, GroupMessageEvent):
        group_id: str = str(event.group_id)
        # 在允许的群聊中启用
        if group_id in enabled_groups:
            # 不回复黑名单用户
            return group_id not in ban_user.keys() or user_id not in ban_user[group_id]
        return False
    # 启用私聊
    return True


async def is_admin(bot: Bot, event: MessageEvent, state: T_State) -> bool:
    if not await to_me()(bot, event, state):
        return False
    user_id: str = event.get_user_id()
    if isinstance(event, GroupMessageEvent):
        group_id: str = str(event.group_id)
        user_info: dict = await bot.call_api(
            "get_group_member_info", **{"group_id": group_id, "user_id": user_id}
        )
        user_role: str = user_info["role"]
        # 只允许管理员使用
        if user_role in ["owner", "admin"]:
            return True
        return False
    # 禁用私聊
    return False


commandConfig = CommandGroup("wftconfig", rule=is_admin)
commandEnable = commandConfig.command("enable", aliases={"启用"})
commandDisable = commandConfig.command("disable", aliases={"禁用"})
commandBan = commandConfig.command("ban", aliases={"拉黑"})
commandUnban = commandConfig.command("unban", aliases={"解禁"})


@commandEnable.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg()):
    global enabled_groups
    group_id = str(event.group_id)
    if group_id in enabled_groups:
        await commandEnable.finish(f"群聊 {group_id} 已在白名单中")
    enabled_groups.add(group_id)
    await commandEnable.send(f"群聊 {group_id} 加入了白名单")


@commandDisable.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg()):
    global enabled_groups
    group_id = str(event.group_id)
    if group_id not in enabled_groups:
        await commandDisable.finish(f"群聊 {group_id} 不在白名单中")
    enabled_groups.remove(group_id)
    await commandDisable.send(f"群聊 {group_id} 退出了白名单")


@commandBan.handle()
async def _(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    global ban_user
    ban_users: list[str] = [
        x for x in args.extract_plain_text().split(" ") if x.isdigit()
    ]
    group_id = str(event.group_id)
    if group_id not in enabled_groups:
        await commandBan.finish(f"群聊 {group_id} 不在白名单中")
    for user_id in ban_users:
        if user_id in ban_user[group_id]:
            await commandBan.send(
                f"{(await bot.call_api("get_group_member_info", **{"group_id":group_id, "user_id": user_id}))["nickname"]} 已在群聊 {group_id} 的黑名单中"
            )
        ban_user[group_id].add(user_id)
        await commandBan.send(
            f"在群聊 {group_id} 中拉黑了 {(await bot.call_api("get_group_member_info", **{"group_id":group_id, "user_id": user_id}))["nickname"]}"
        )


@commandUnban.handle()
async def _(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    global ban_user
    unban_users: list[str] = [
        x for x in args.extract_plain_text().split(" ") if x.isdigit()
    ]
    group_id = str(event.group_id)
    if group_id not in enabled_groups:
        await commandUnban.finish(f"群聊 {group_id} 不在白名单中")
    for user_id in unban_users:
        if user_id not in ban_user[group_id]:
            await commandUnban.send(
                f"{(await bot.call_api("get_group_member_info", **{"group_id":group_id, "user_id": user_id}))["nickname"]} 不在群聊 {group_id} 的黑名单中"
            )
        ban_user[group_id].remove(user_id)
        await commandUnban.send(
            f"在群聊 {group_id} 中解禁了 {(await bot.call_api("get_group_member_info", **{"group_id":group_id, "user_id": user_id}))["nickname"]}"
        )


commandPrefix = CommandGroup("wft", rule=is_enabled)

commandInit = commandPrefix.command("init", aliases={"创建", "开房", "初始化"})
commandEnd = commandPrefix.command("end", aliases={"结束", "中止"}, rule=to_me())

commandJoin = commandPrefix.command("join", aliases={"加入", "加", "进入", "进"})
commandExit = commandPrefix.command("exit", aliases={"退出", "退", "离开", "离"})
commandAddrole = commandPrefix.command("addrole", aliases={"添角色", "添"})
commandRmrole = commandPrefix.command("rmrole", aliases={"删角色", "删"})
commandShowroles = commandPrefix.command("showroles", aliases={"显示角色", "显"})
commandAutoroles = commandPrefix.command("autoroles", aliases={"自动角色", "自动"})
commandStart = commandPrefix.command("start", aliases={"开始", "启动"})

commandAction = commandPrefix.command("action", aliases={"行动", "药", "刀", "查"})
commandSkill = commandPrefix.command("skill", aliases={"技能", "爆", "枪", "决斗"})
commandSkip = commandPrefix.command("skip", aliases={"跳过", "过", "不使用技能"})


games: dict[str, Game] = {}


@commandInit.handle()
async def _(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    global games
    groupId: str = str(event.group_id)
    if groupId in games.keys() and games[groupId]:
        await commandInit.finish("请先结束上一局游戏. ")
    games[groupId] = Game(groupId, BotIO(bot))
    await commandInit.finish("游戏已创建")


@commandEnd.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg()):
    global games
    groupId: str = str(event.group_id)
    if groupId not in games.keys() or not games[groupId]:
        await commandEnd.finish("没有正在进行的游戏. ")
    games[groupId].endsUp()
    del games[groupId]
    await commandEnd.finish("游戏已结束")


@commandJoin.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg()):
    global games
    groupId: str = str(event.group_id)
    if groupId not in games.keys() or not games[groupId]:
        await commandEnd.finish("没有正在进行的游戏. ")
    playerId: str = event.get_user_id()
    if playerId in games[groupId].playerList:
        await commandJoin.finish("不能重复加入游戏")
    games[groupId].addPlayer(playerId)
    await commandJoin.finish(Message(f"[CQ:at,qq={str(int(playerId))}] 已加入游戏"))


@commandExit.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg()):
    global games
    groupId: str = str(event.group_id)
    if groupId not in games.keys() or not games[groupId]:
        await commandEnd.finish("没有正在进行的游戏. ")
    playerId: str = event.get_user_id()
    games[groupId].removePlayer(games[groupId].playerList.index(playerId))
    await commandExit.finish(Message(f"[CQ:at,qq={str(int(playerId))}] 已离开游戏"))


@commandAddrole.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg()):
    global games
    groupId: str = str(event.group_id)
    if groupId not in games.keys() or not games[groupId]:
        await commandEnd.finish("没有正在进行的游戏. ")
    roleList = args.extract_plain_text().split(" ")
    roleClasses: list[roles.RoleBase] = [
        x for x in get_classes_in_module(roles) if issubclass(x, roles.RoleBase)
    ]
    for roleName in roleList:
        tps: list[roles.RoleBase] = [
            x() for x in roleClasses if roleName in x.typeAlias
        ]
        if len(tps) > 1:
            logger.warning(
                f"Other items with the same name ({roleName}) are ignored. e.g.{tps[1:]}"
            )
        if len(tps) == 0:
            await commandAutoroles.send(f"非法的角色名 {roleName}")
            continue
        games[groupId].addRole(tps[0])
        await commandAddrole.send(f"已添加角色 {tps[0].getType()}")


@commandRmrole.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg()):
    global games
    groupId: str = str(event.group_id)
    if groupId not in games.keys() or not games[groupId]:
        await commandEnd.finish("没有正在进行的游戏. ")
    roleList = args.extract_plain_text().split(" ")
    for roleName in roleList:
        if roleName is int:
            pos = roleName
        else:
            for i in range(len(games[groupId].roleList)):
                if roleName in games[groupId].roleList[i].typeAlias:
                    pos = i
        tp = games[groupId].roleList[pos].getType()
        games[groupId].removeRole(pos)
        await commandAddrole.send(f"已删除角色 {tp}")


@commandShowroles.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg()):
    global games
    groupId: str = str(event.group_id)
    if groupId not in games.keys() or not games[groupId]:
        await commandEnd.finish("没有正在进行的游戏. ")
    await commandShowroles.send(
        f"角色列表: {[x.getType() for x in games[groupId].roleList]}"
    )


@commandAutoroles.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg()):
    global games
    groupId: str = str(event.group_id)
    if groupId not in games.keys() or not games[groupId]:
        await commandEnd.finish("没有正在进行的游戏. ")
    if error := games[groupId].useDefaultRoleLists():
        await commandAutoroles.finish(error)


@commandStart.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg()):
    global games
    groupId: str = str(event.group_id)
    if groupId not in games.keys() or not games[groupId]:
        await commandEnd.finish("没有正在进行的游戏. ")
    if error := games[groupId].start():
        if error[-1:-3] == "获胜":
            await games[groupId].endsUp()
            del games[groupId]
        await commandStart.finish(error)


@commandAction.handle()
async def _(event: PrivateMessageEvent, args: Message = CommandArg()):
    global games
    userId: str = event.get_user_id()
    try:
        myGame = [x for x in games.values() if userId in x.playerList][0]
    except:
        await commandAction.finish("你未加入游戏")
    try:
        role = [x for x in myGame.roleList if x.name == userId][0]
    except:
        await commandAction.finish("你还没有角色")
    if not role.canAction:
        await commandAction.finish("你还不能行动")
    try:
        role.action(
            games[myGame.groupId],
            games[myGame.groupId].io,
            args.extract_plain_text().split(" "),
        )
    except ValueError:
        await commandAction.finish("非法的参数值")
    role.canAction = False
    if error := myGame._nightActions():
        if error[-1:-3] == "获胜":
            await games[myGame.groupId].endsUp()
            del games[myGame.groupId]


@commandSkip.handle()
async def _(event: PrivateMessageEvent, args: Message = CommandArg()):
    global games
    userId: str = event.get_user_id()
    try:
        myGame = [x for x in games.values() if userId in x.playerList][0]
    except:
        await commandAction.finish("你未加入游戏")
    try:
        role = [x for x in myGame.roleList if x.name == userId][0]
    except:
        await commandAction.finish("你还没有角色")
    if role.canAction:
        role.canAction = False
        if error := myGame._nightActions():
            if error[-1:-3] == "获胜":
                await games[myGame.groupId].endsUp()
                del games[myGame.groupId]
    elif role.canUseSkill:
        role.canUseSkill = False
    else:
        await commandAction.finish("你还不能操作")
