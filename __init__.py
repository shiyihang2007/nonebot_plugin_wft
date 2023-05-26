# 命令处理


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
    pass


@commandJoin.handle()
async def commandJoinHandle(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    pass


@commandConfig.handle()
async def commandConfigHandle(
    bot: Bot, event: MessageEvent, arg: Message = CommandArg()
):
    pass


@commandStart.handle()
async def commandStartHandle(
    bot: Bot, event: MessageEvent, arg: Message = CommandArg()
):
    pass


@commandSkill.handle()
async def commandSkillHandle(
    bot: Bot, event: MessageEvent, arg: Message = CommandArg()
):
    pass


@commandEnd.handle()
async def commandEndHandle(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    pass
