"""
nonebot_plugin_wft
"""

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
from nonebot.rule import to_me
from nonebot.log import logger

from .game import Game
from .botio import BotIO
from . import roles

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
    """
    is_enabled 判断插件是否启用
    """
    user_id: str = event.get_user_id()
    if isinstance(event, GroupMessageEvent):
        group_id: str = str(event.group_id)
        # 在允许的群聊中启用
        if group_id in enabled_groups:
            # 不回复黑名单用户
            return group_id not in ban_user or user_id not in ban_user[group_id]
        return False
    # 启用私聊
    return True


async def is_admin(bot: Bot, event: MessageEvent, state: T_State) -> bool:
    """
    is_admin 判断调用者是否为管理
    """
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


CommandConfig = CommandGroup("wftconfig", rule=is_admin)
CommandEnable = CommandConfig.command("enable", aliases={"启用"})
CommandDisable = CommandConfig.command("disable", aliases={"禁用"})
CommandBan = CommandConfig.command("ban", aliases={"拉黑"})
CommandUnban = CommandConfig.command("unban", aliases={"解禁"})


@CommandEnable.handle()
async def _(event: GroupMessageEvent):
    group_id = str(event.group_id)
    if group_id in enabled_groups:
        await CommandEnable.finish(f"群聊 {group_id} 已在白名单中")
    enabled_groups.add(group_id)
    await CommandEnable.send(f"群聊 {group_id} 加入了白名单")


@CommandDisable.handle()
async def _(event: GroupMessageEvent):
    group_id = str(event.group_id)
    if group_id not in enabled_groups:
        await CommandDisable.finish(f"群聊 {group_id} 不在白名单中")
    enabled_groups.remove(group_id)
    await CommandDisable.send(f"群聊 {group_id} 退出了白名单")


@CommandBan.handle()
async def _(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    ban_users: list[str] = [
        x for x in args.extract_plain_text().split(" ") if x.isdigit()
    ]
    group_id = str(event.group_id)
    if group_id not in enabled_groups:
        await CommandBan.finish(f"群聊 {group_id} 不在白名单中")
    for user_id in ban_users:
        if user_id in ban_user[group_id]:
            await CommandBan.send(
                f"""{
                    (
                        await bot.call_api(
                            "get_group_member_info",
                            **{"group_id": group_id, "user_id": user_id},
                        )
                    )["nickname"]
                } 已在群聊 {group_id} 的黑名单中"""
            )
        ban_user[group_id].add(user_id)
        await CommandBan.send(
            f"""在群聊 {group_id} 中拉黑了 {
                (
                    await bot.call_api(
                        "get_group_member_info",
                        **{"group_id": group_id, "user_id": user_id},
                    )
                )["nickname"]
            }"""
        )


@CommandUnban.handle()
async def _(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    unban_users: list[str] = [
        x for x in args.extract_plain_text().split(" ") if x.isdigit()
    ]
    group_id = str(event.group_id)
    if group_id not in enabled_groups:
        await CommandUnban.finish(f"群聊 {group_id} 不在白名单中")
    for user_id in unban_users:
        if user_id not in ban_user[group_id]:
            await CommandUnban.send(
                f"""{
                    (
                        await bot.call_api(
                            "get_group_member_info",
                            **{"group_id": group_id, "user_id": user_id},
                        )
                    )["nickname"]
                } 不在群聊 {group_id} 的黑名单中"""
            )
        ban_user[group_id].remove(user_id)
        await CommandUnban.send(
            f"""在群聊 {group_id} 中解禁了 {
                (
                    await bot.call_api(
                        "get_group_member_info",
                        **{"group_id": group_id, "user_id": user_id},
                    )
                )["nickname"]
            }"""
        )


commandPrefix = CommandGroup("wft", rule=is_enabled)

CommandInit = commandPrefix.command("init", aliases={"创建", "开房", "初始化"})
CommandEnd = commandPrefix.command("end", aliases={"结束", "中止"}, rule=to_me())

CommandJoin = commandPrefix.command("join", aliases={"加入", "加", "进入", "进"})
CommandExit = commandPrefix.command("exit", aliases={"退出", "退", "离开", "离"})
CommandAddrole = commandPrefix.command("addrole", aliases={"添角色", "添"})
CommandRmrole = commandPrefix.command("rmrole", aliases={"删角色", "删"})
CommandShowroles = commandPrefix.command("showroles", aliases={"显示角色", "显"})
CommandAutoroles = commandPrefix.command("autoroles", aliases={"自动角色", "自动"})
CommandStart = commandPrefix.command("start", aliases={"开始", "启动"})

CommandAction = commandPrefix.command("action", aliases={"行动", "药", "刀", "查"})
CommandSkill = commandPrefix.command("skill", aliases={"技能", "爆", "枪", "决斗"})
CommandSkip = commandPrefix.command("skip", aliases={"跳过", "过", "不使用技能"})


games: dict[str, Game] = {}


@CommandInit.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    group_id: str = str(event.group_id)
    if group_id in games and games[group_id]:
        await CommandInit.finish("请先结束上一局游戏. ")
    games[group_id] = Game(group_id, BotIO(bot))
    await CommandInit.finish("游戏已创建")


@CommandEnd.handle()
async def _(event: GroupMessageEvent):
    group_id: str = str(event.group_id)
    if group_id not in games or not games[group_id]:
        await CommandEnd.finish("没有正在进行的游戏. ")
    games[group_id].endsUp()
    del games[group_id]
    await CommandEnd.finish("游戏已结束")


@CommandJoin.handle()
async def _(event: GroupMessageEvent):
    group_id: str = str(event.group_id)
    if group_id not in games or not games[group_id]:
        await CommandEnd.finish("没有正在进行的游戏. ")
    player_id: str = event.get_user_id()
    if player_id in games[group_id].playerList:
        await CommandJoin.finish("不能重复加入游戏")
    games[group_id].addPlayer(player_id)
    await CommandJoin.finish(Message(f"[CQ:at,qq={str(int(player_id))}] 已加入游戏"))


@CommandExit.handle()
async def _(event: GroupMessageEvent):
    group_id: str = str(event.group_id)
    if group_id not in games or not games[group_id]:
        await CommandEnd.finish("没有正在进行的游戏. ")
    player_id: str = event.get_user_id()
    games[group_id].removePlayer(games[group_id].playerList.index(player_id))
    await CommandExit.finish(Message(f"[CQ:at,qq={str(int(player_id))}] 已离开游戏"))


@CommandAddrole.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg()):
    group_id: str = str(event.group_id)
    if group_id not in games or not games[group_id]:
        await CommandEnd.finish("没有正在进行的游戏. ")
    role_list = args.extract_plain_text().split(" ")
    role_classes: list[type[roles.RoleBase]] = [
        x for x in get_classes_in_module(roles) if issubclass(x, roles.RoleBase)
    ]
    for role_name in role_list:
        tps: list[roles.RoleBase] = [
            x() for x in role_classes if role_name in x.typeAlias
        ]
        if len(tps) > 1:
            logger.warning(
                f"Other items with the same name ({role_name}) are ignored. e.g.{tps[1:]}"
            )
        if len(tps) == 0:
            await CommandAutoroles.send(f"非法的角色名 {role_name}")
            continue
        games[group_id].addRole(tps[0])
        await CommandAddrole.send(f"已添加角色 {tps[0].getType()}")


@CommandRmrole.handle()
async def _(event: GroupMessageEvent, args: Message = CommandArg()):
    group_id: str = str(event.group_id)
    if group_id not in games or not games[group_id]:
        await CommandEnd.finish("没有正在进行的游戏. ")
    role_list: list[str] = args.extract_plain_text().split(" ")
    for role_name in role_list:
        pos = -1
        if role_name.isdigit():
            pos = int(role_name)
        else:
            for i in range(len(games[group_id].roleList)):
                if role_name in games[group_id].roleList[i].typeAlias:
                    pos = i
        if pos != -1:
            tp = games[group_id].roleList[pos].getType()
            games[group_id].removeRole(pos)
            await CommandAddrole.send(f"已删除角色 {tp}")
        await CommandAddrole.send(f"角色 {role_name} 不存在")


@CommandShowroles.handle()
async def _(event: GroupMessageEvent):
    group_id: str = str(event.group_id)
    if group_id not in games or not games[group_id]:
        await CommandEnd.finish("没有正在进行的游戏. ")
    await CommandShowroles.send(
        f"角色列表: {[x.getType() for x in games[group_id].roleList]}"
    )


@CommandAutoroles.handle()
async def _(event: GroupMessageEvent):
    group_id: str = str(event.group_id)
    if group_id not in games or not games[group_id]:
        await CommandEnd.finish("没有正在进行的游戏. ")
    if error := games[group_id].useDefaultRoleLists():
        await CommandAutoroles.finish(error)


@CommandStart.handle()
async def _(event: GroupMessageEvent):
    group_id: str = str(event.group_id)
    if group_id not in games or not games[group_id]:
        await CommandEnd.finish("没有正在进行的游戏. ")
    if error := games[group_id].start():
        if error[-1:-3] == "获胜":
            games[group_id].endsUp()
            del games[group_id]
        await CommandStart.finish(error)


@CommandAction.handle()
async def _(event: PrivateMessageEvent, args: Message = CommandArg()):
    user_id: str = event.get_user_id()
    try:
        my_game = [x for x in games.values() if user_id in x.playerList][0]
    except IndexError:
        await CommandAction.finish("你未加入游戏")
    try:
        role = [x for x in my_game.roleList if x.name == user_id][0]
    except IndexError:
        await CommandAction.finish("你还没有角色")
    if not role.canAction:
        await CommandAction.finish("你还不能行动")
    try:
        role.action(
            games[my_game.groupId],
            games[my_game.groupId].io,
            args.extract_plain_text().split(" "),
        )
    except ValueError:
        await CommandAction.finish("非法的参数值")
    role.canAction = False
    if error := my_game.nightActions():
        if error[-1:-3] == "获胜":
            games[my_game.groupId].endsUp()
            del games[my_game.groupId]


@CommandSkip.handle()
async def _(event: PrivateMessageEvent):
    user_id: str = event.get_user_id()
    try:
        my_game = [x for x in games.values() if user_id in x.playerList][0]
    except IndexError:
        await CommandAction.finish("你未加入游戏")
    try:
        role = [x for x in my_game.roleList if x.name == user_id][0]
    except IndexError:
        await CommandAction.finish("你还没有角色")
    if role.canAction:
        role.canAction = False
        if error := my_game.nightActions():
            if error[-1:-3] == "获胜":
                games[my_game.groupId].endsUp()
                del games[my_game.groupId]
    elif role.canUseSkill:
        role.canUseSkill = False
    else:
        await CommandAction.finish("你还不能操作")
