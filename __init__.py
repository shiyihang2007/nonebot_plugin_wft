# 命令处理
import src.plugins.nonebot_plugin_wft.rules

from nonebot.adapters.onebot.v11 import Bot, Message, MessageEvent
from nonebot import (
    CommandGroup,
)
from nonebot.params import CommandArg

# require("nonebot_plugin_datastore")
# from nonebot_plugin_datastore import PluginData


commandPrefix = CommandGroup("wft")

commandInit = commandPrefix.command("init", aliases={"创建", "开房", "初始化"})
commandJoin = commandPrefix.command("join", aliases={"加入", "加", "进入", "进"})
commandConfig = commandPrefix.command("config", aliases={"自定义", "设置", "配置"})
commandStart = commandPrefix.command("start", aliases={"开始", "启动"})
commandSkill = commandPrefix.command("skill", aliases={"技能", "救", "刀", "查", "救", "毒"})
commandEnd = commandPrefix.command("end", aliases={"结束", "放弃"})


@commandInit.handle()
async def commandInitHandle(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    await commandInit.send(
        await src.plugins.nonebot_plugin_wft.rules.wfInit(bot, event, arg)
    )


@commandJoin.handle()
async def commandJoinHandle(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    await commandJoin.send(
        await src.plugins.nonebot_plugin_wft.rules.wfJoin(bot, event, arg)
    )


@commandConfig.handle()
async def commandConfigHandle(
    bot: Bot, event: MessageEvent, arg: Message = CommandArg()
):
    await commandConfig.send(
        await src.plugins.nonebot_plugin_wft.rules.wfConfig(bot, event, arg)
    )


@commandStart.handle()
async def commandStartHandle(
    bot: Bot, event: MessageEvent, arg: Message = CommandArg()
):
    await src.plugins.nonebot_plugin_wft.rules.wfStart(bot, event, arg)


@commandSkill.handle()
async def commandSkillHandle(
    bot: Bot, event: MessageEvent, arg: Message = CommandArg()
):
    await src.plugins.nonebot_plugin_wft.rules.wfNightSkillProc(bot, event, arg)


@commandEnd.handle()
async def commandEndHandle(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    await commandEnd.send(
        await src.plugins.nonebot_plugin_wft.rules.wfGiveUp(bot, event, arg)
    )
