from nonebot.adapters.onebot.v11 import Bot, Message, MessageEvent
from .player import player
from .units import type2RoleSkill, type2RoleSkillHint, type2RoleStr


class game:
    group: str = ""
    players: list[player] = []
    config: list[int] = []
    deathList: list[int] = []

    async def init(self, bot: Bot, event: MessageEvent, arg: Message) -> None:
        """
        - 初始化
        - 不做会话类型判断
        """
        if len(event.get_session_id().split("-")[1]) < 5:
            raise ValueError
        self.group = event.get_session_id().split("_")[1]
        self.config = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        self.deathList = []
        await self.customConfig(bot, event, arg)

    async def customConfig(self, bot: Bot, event: MessageEvent, arg: Message) -> None:
        """
        - 自定义设置 类型:数量
        - 类型 人 狼 预言 女巫 守卫 骑士 猎人 黑狼 白狼 隐狼 白痴
        - 不做会话类型判断
        """
        if event.message_type != "group":
            await bot.send(event, "请在群聊中使用")
            return
        if len(arg) < 1:
            return
        args: list[str] = arg.extract_plain_text().split()
        res: str = "自定义参数"
        for i in args:
            input: list[str] = i.split(":")
            if len(input) < 2:
                res += f"{input} 不合法"
                continue
            # TODO 别名判断
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
            elif input[0] == "痴":
                self.config[1] = int(input[1])
            else:
                res += f"{input} 不合法"
                continue
            res += f"已将 {input[0]} 数量设为 {int(input[1])}"
        await bot.send(event, res)

    async def join(self, bot: Bot, event: MessageEvent, arg: Message) -> None:
        """
        - 加入
        - 不做会话类型判断
        """
        thisPlayer = player()
        thisPlayer.qq = event.get_user_id()
        thisPlayer.death = False
        thisPlayer.id = len(self.players) + 1
        thisPlayer.role = ""
        self.players.append(thisPlayer)
        await bot.send(
            event,
            (
                f"玩家 {thisPlayer.qq} 已成功加入群组 {self.group} 中的游戏\n"
                "当前人数 {len(self.players)}"
            ),
        )

    async def start(self, bot: Bot, event: MessageEvent, arg: Message) -> None:
        """
        - 启动
        - 分配身份
        - 发送身份
        """
        # TODO 身份分配
        # TODO 发送身份
        pass

    async def night(self, bot: Bot) -> None:
        """
        - 夜晚流程
        - 使用技能
        - 下一个角色 / 进入白天
        """
        pass

    async def sendSkill(self, bot: Bot, players: list[player]) -> None:
        """
        - 发送技能
        - `players: list[player]` 需要发送到的玩家列表
        """
        pass

    async def skillWork(self, fromPlayer: player, toPlayer: player) -> None:
        """
        - 处理技能
        - `fromPlayer: player` 技能发起方
        - `toPlayer: player` 技能接受方
        """
        pass

    async def discuss(self) -> None:
        '''
        - 轮流发言 邀请
        '''
        pass

    async def discussSkip(self) -> None:
        '''
        - 轮流发言 结束
        '''
        pass

    async def sendDeath(self) -> None:
        '''
        - 发送死亡信息
        '''
        pass
