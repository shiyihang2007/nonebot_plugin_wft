from nonebot.adapters.onebot.v11 import Bot, Message


class BotIO:

    bot: Bot

    def __init__(self, _bot):
        self.bot = _bot

    async def privateSend(self, userId: str, msg: Message):
        await self.bot.send_private_msg(user_id=int(userId), message=msg)

    async def groupSend(self, groupId: str, msg: Message):
        await self.bot.send_group_msg(group_id=int(groupId), message=msg)

    async def setGroupUserName(self, groupId: str, userId: str, name: str):
        await self.bot.set_group_card(
            group_id=int(groupId), user_id=int(userId), card=name
        )
