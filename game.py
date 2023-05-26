from nonebot.adapters.onebot.v11 import Bot, Message, MessageEvent
from .player import player


class game:
    group: str = ""
    players: list[player] = []
    config: list[str] = []

    # 配置 人 狼 预言 女巫 守卫 骑士 猎人 黑狼 白狼 隐狼 白痴
    def init(self, bot: Bot, event: MessageEvent, arg: Message):
        self.config = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        self.customConfig(bot, event, arg)

    # 自定义设置 类型:数量
    def customConfig(self, bot: Bot, event: MessageEvent, arg: Message):
        args: list[str] = arg.extract_plain_text().split()
        for i in args:
            input = i.split(":")
            if len(input) < 2:
                bot.send(event, f"{input} 不合法")
                continue
            if input[0] == "人":
                self.config[0] = int(input[1])
            elif input[0] == "狼":
                self.config[1] = int(input[1])
            elif input[0] == "预":
                self.config[2] = int(input[1])
            elif input[0] == "女":
                self.config[3] = int(input[1])
            elif input[0] == "守":
                self.config[4] = int(input[1])
            elif input[0] == "骑":
                self.config[5] = int(input[1])
            elif input[0] == "猎":
                self.config[6] = int(input[1])
            elif input[0] == "黑":
                self.config[7] = int(input[1])
            elif input[0] == "白":
                self.config[8] = int(input[1])
            elif input[0] == "隐":
                self.config[9] = int(input[1])
            elif input[0] == "chi":
                self.config[1] = int(input[1])
            else:
                bot.send(event, f"{input} 不合法")
                continue
            bot.send(event, f"已将 {input[0]} 数量设为 {int(input[1])}")
