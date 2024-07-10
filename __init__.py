# 命令处理
import nonebot
from game import Game
from botio import BotIO

from nonebot.adapters.onebot.v11 import Bot, Message, MessageEvent, GroupMessageEvent
from nonebot import (
    CommandGroup,
)
from nonebot.params import CommandArg
from nonebot.rule import to_me

# require("nonebot_plugin_datastore")
# from nonebot_plugin_datastore import PluginData


commandPrefix = CommandGroup("wft")

commandInit = commandPrefix.command("init", aliases={"创建", "开房", "初始化"})
commandEnd = commandPrefix.command("end", aliases={"结束", "中止"}, rule=to_me())
commandJoin = commandPrefix.command("join", aliases={"加入", "加", "进入", "进"})
commandExit = commandPrefix.command("exit", aliases={"退出", "退", "离开", "离"})
commandConfig = commandPrefix.command("config", aliases={"自定义", "设置", "配置"})
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
