from nonebot.adapters.onebot.v11 import Bot, Message


async def privateSend(bot: Bot, userId: str, msg: Message):
    await bot.send_private_msg(user_id=int(userId), message=msg)


async def groupSend(bot: Bot, groupId: str, msg: Message):
    await bot.send_group_msg(group_id=int(groupId), message=msg)


async def setGroupUserName(bot: Bot, groupId: str, userId: str, name: str):
    await bot.set_group_card(group_id=int(groupId), user_id=int(userId), card=name)
