"""
nonebot_plugin_wft

基于 NoneBot2 + OneBot v11 的房间制狼人杀插件。

说明
- 游戏以群为单位创建房间；私聊用于夜晚技能等隐私操作（`wft.skill ...`、`wft.skip`）。
- 大部分指令仅允许在群聊中使用（例如 init/join/start/vote）。
"""

from __future__ import annotations

from nonebot.adapters.onebot.v11 import (
    Bot,
    Message,
    MessageEvent,
    GroupMessageEvent,
)
from nonebot import (
    CommandGroup,
)
from nonebot.typing import T_State
from nonebot.params import CommandArg
from nonebot.rule import to_me
from nonebot.permission import SUPERUSER

from .game.room import Room, get_character_class_by_role_id
from .room_manager import RoomManager

from nonebot import require
from pathlib import Path

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store

# require("nonebot_plugin_datastore")
# from nonebot_plugin_datastore import PluginData

(store.get_plugin_data_dir() / "enabled_groups.txt").touch(exist_ok=True)
enalbed_groups_file = store.get_plugin_data_file("enabled_groups.txt")

def get_enabled_groups() -> set[str]:
    groups: set[str] = set()
    group_ids = enalbed_groups_file.read_text().splitlines()
    for group_id in group_ids:
        groups.add(group_id)
    return groups

ban_user: dict[str, set[str]] = {}
enabled_groups: set[str] = get_enabled_groups()


async def is_enabled(event: MessageEvent) -> bool:
    """规则：插件是否响应当前事件。

    - 群聊：仅当群号在白名单中，且调用者未被拉黑时启用。
    - 私聊：允许（各 handler 仍需自行校验哪些指令允许在私聊中使用）。
    """
    user_id: str = event.get_user_id()
    if isinstance(event, GroupMessageEvent):
        group_id: str = str(event.group_id)
        # 在允许的群聊中启用
        if group_id in enabled_groups:
            # 不回复黑名单用户
            return group_id not in ban_user or user_id not in ban_user[group_id]
        return False
    # 启用私聊（用于夜晚技能等隐私操作）
    return True


async def is_admin(bot: Bot, event: MessageEvent, state: T_State) -> bool:
    """规则：仅群管理员（owner/admin）可用，且必须 @机器人。"""
    if not await to_me()(bot, event, state):
        return False
    user_id: str = event.get_user_id()
    if isinstance(event, GroupMessageEvent):
        user_info: dict = await bot.call_api(
            "get_group_member_info",
            **{"group_id": event.group_id, "user_id": int(user_id)},
        )
        user_role: str = user_info["role"]
        # 只允许管理员使用
        if user_role in ["owner", "admin"] or await SUPERUSER(bot, event):
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
    enabled_groups_list = [s for s in list(enabled_groups) if s != group_id]
    enalbed_groups_file.write_text("\n".join(enabled_groups_list))
    await CommandEnable.send(f"群聊 {group_id} 加入了白名单")


@CommandDisable.handle()
async def _(event: GroupMessageEvent):
    group_id = str(event.group_id)
    if group_id not in enabled_groups:
        await CommandDisable.finish(f"群聊 {group_id} 不在白名单中")
    enabled_groups.remove(group_id)
    enabled_groups_list = [s for s in list(enabled_groups) if s != group_id]
    enalbed_groups_file.write_text("\n".join(enabled_groups_list))
    await CommandDisable.send(f"群聊 {group_id} 退出了白名单")


@CommandBan.handle()
async def _(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    ban_users: list[str] = [
        x for x in args.extract_plain_text().split(" ") if x.isdigit()
    ]
    group_id = str(event.group_id)
    if group_id not in enabled_groups:
        await CommandBan.finish(f"群聊 {group_id} 不在白名单中")

    group_ban_user = ban_user.setdefault(group_id, set())
    for user_id in ban_users:
        nickname = (
            await bot.call_api(
                "get_group_member_info",
                **{"group_id": event.group_id, "user_id": int(user_id)},
            )
        )["nickname"]

        if user_id in group_ban_user:
            await CommandBan.send(f"{nickname} 已在群聊 {group_id} 的黑名单中")
            continue

        group_ban_user.add(user_id)
        await CommandBan.send(f"在群聊 {group_id} 中拉黑了 {nickname}")


@CommandUnban.handle()
async def _(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    unban_users: list[str] = [
        x for x in args.extract_plain_text().split(" ") if x.isdigit()
    ]
    group_id = str(event.group_id)
    if group_id not in enabled_groups:
        await CommandUnban.finish(f"群聊 {group_id} 不在白名单中")

    group_ban_user = ban_user.setdefault(group_id, set())
    for user_id in unban_users:
        nickname = (
            await bot.call_api(
                "get_group_member_info",
                **{"group_id": event.group_id, "user_id": int(user_id)},
            )
        )["nickname"]

        if user_id not in group_ban_user:
            await CommandUnban.send(f"{nickname} 不在群聊 {group_id} 的黑名单中")
            continue

        group_ban_user.remove(user_id)
        await CommandUnban.send(f"在群聊 {group_id} 中解禁了 {nickname}")


commandPrefix = CommandGroup("wft", rule=is_enabled)

CommandInit = commandPrefix.command("init", aliases={"i", "创建", "开房", "初始化"})
CommandEnd = commandPrefix.command("end", aliases={"结束", "中止"}, rule=to_me())
CommandDebug = commandPrefix.command("debug", rule=to_me())

CommandJoin = commandPrefix.command("join", aliases={"j", "加入", "加", "进入", "进"})
CommandExit = commandPrefix.command("exit", aliases={"e", "退出", "退", "离开", "离"})
CommandShowroles = commandPrefix.command("showplayers", aliases={"显示玩家", "玩家"})

CommandAddrole = commandPrefix.command("addrole", aliases={"a", "添角色", "添"})
CommandRmrole = commandPrefix.command("rmrole", aliases={"r", "删角色", "删"})
CommandShowroles = commandPrefix.command(
    "showroles", aliases={"d", "displayroles", "显示角色", "显"}
)
CommandAutoroles = commandPrefix.command(
    "autoroles", aliases={"ar", "自动角色", "自动"}
)
CommandStart = commandPrefix.command("start", aliases={"s", "开始", "启动"})

CommandSkill = commandPrefix.command(
    "skill", aliases={"u", "use", "用", "技能", "用技能"}
)
CommandVote = commandPrefix.command("vote", aliases={"v", "投", "投票"})
CommandSkip = commandPrefix.command(
    "skip", aliases={"p", "pass", "跳过", "过", "不用", "不使用技能"}
)

_room_manager = RoomManager()


def _resolve_room_for_private_user(
    user_id: str,
) -> tuple[str | None, Room | None, str | None]:
    """为发起私聊指令的用户选择目标房间。

    一个用户理论上可能同时在多个群的房间中。此时策略是：
    - 若只有一个房间处于 `night`，优先选择该房间（常见于夜晚私聊技能）。
    - 否则返回歧义提示，要求用户显式指定群号。
    """

    candidates: list[tuple[str, Room]] = [
        (gid, room)
        for gid, room in _room_manager.rooms.items()
        if user_id in room.id_2_player and room.state != "ended"
    ]
    if not candidates:
        return None, None, "你不在任何进行中的游戏中。"
    if len(candidates) == 1:
        return candidates[0][0], candidates[0][1], None

    night_candidates = [c for c in candidates if c[1].state == "night"]
    if len(night_candidates) == 1:
        return night_candidates[0][0], night_candidates[0][1], None

    group_list = ", ".join(gid for gid, _ in candidates)
    return (
        None,
        None,
        "你同时在多个群的游戏中"
        f"({group_list}), 请指定群号。\n"
        "示例: `wft.skill -g <群号> <动作> [参数]` / `wft.skill <群号> <动作> [参数]`；"
        "`wft.skip -g <群号>` / `wft.skip <群号>`",
    )


def _extract_group_id_hint(
    tokens: list[str],
) -> tuple[str | None, list[str], str | None]:
    """从 token 列表开头解析可选的群号提示。

    支持的语法（主要用于私聊指令）：
    - `wft.skill -g <群号> ...`
    - `wft.skip -g <群号>`
    - `wft.skill <群号> ...`（仅当数字看起来像群号时才会当作群号）
    - `wft.skip <群号>`
    """

    if not tokens:
        return None, tokens, None

    if tokens[0] in {"-g", "--group"}:
        if len(tokens) < 2 or not tokens[1].isdigit():
            return None, tokens, "用法：`wft.skill -g <群号> <动作> [参数]`"
        return tokens[1], tokens[2:], None

    if tokens[0].isdigit() and (
        tokens[0] in _room_manager.rooms or len(tokens[0]) >= 5
    ):
        return tokens[0], tokens[1:], None

    return None, tokens, None


@CommandInit.handle()
async def _(bot: Bot, event: MessageEvent):
    if not isinstance(event, GroupMessageEvent):
        await CommandInit.finish("请在群聊中使用该指令。")
    group_id: str = str(event.group_id)
    async with _room_manager.lock(group_id):
        old_room = _room_manager.rooms.get(group_id)
        if old_room:
            if old_room.state != "ended":
                await CommandInit.finish("请先结束上一局游戏. ")

            new_room = Room(group_id, bot.send_group_msg, bot.send_private_msg)
            for p in old_room.player_list:
                await new_room.add_player(p.user_id)
            new_room.character_enabled = dict(old_room.character_enabled)
            new_room.settings = dict(old_room.settings)

            _room_manager.rooms[group_id] = new_room
            await CommandInit.finish(
                "上一局已结束，已创建新房间（保留玩家与角色配置）。"
            )

        _room_manager.rooms[group_id] = Room(
            group_id, bot.send_group_msg, bot.send_private_msg
        )
        await CommandInit.finish("游戏已创建")


@CommandEnd.handle()
async def _(event: MessageEvent):
    if not isinstance(event, GroupMessageEvent):
        await CommandEnd.finish("请在群聊中使用该指令。")
    group_id: str = str(event.group_id)
    async with _room_manager.lock(group_id):
        if group_id not in _room_manager.rooms or not _room_manager.rooms[group_id]:
            await CommandEnd.finish("没有正在进行的游戏. ")
        await _room_manager.rooms[group_id].events_system.event_game_end.active(
            _room_manager.rooms[group_id], None, []
        )
        await CommandEnd.finish("游戏已结束")


@CommandDebug.handle()
async def _(event: MessageEvent):
    if not isinstance(event, GroupMessageEvent):
        await CommandEnd.finish("请在群聊中使用该指令。")
    group_id: str = str(event.group_id)
    async with _room_manager.lock(group_id):
        if group_id not in _room_manager.rooms or not _room_manager.rooms[group_id]:
            await CommandEnd.finish("没有正在进行的游戏. ")
        _room_manager.rooms[group_id].change_setting(
            "debug",
            not _room_manager.rooms[group_id].settings["debug"]
            if "debug" in _room_manager.rooms[group_id].settings
            else True,
        )
        await CommandEnd.finish(
            f"调试模式已{'开启' if _room_manager.rooms[group_id].settings['debug'] else '关闭'}"
        )


@CommandJoin.handle()
async def _(event: MessageEvent):
    if not isinstance(event, GroupMessageEvent):
        await CommandJoin.finish("请在群聊中使用该指令。")
    group_id: str = str(event.group_id)
    async with _room_manager.lock(group_id):
        if group_id not in _room_manager.rooms or not _room_manager.rooms[group_id]:
            await CommandJoin.finish("没有正在进行的游戏. ")
        room = _room_manager.rooms[group_id]
        if room.state != "lobby":
            await CommandJoin.finish("游戏已开始，无法中途加入。")
        user_id: str = event.get_user_id()
        if user_id in room.id_2_player:
            await CommandJoin.finish("不能重复加入游戏")
        await room.add_player(user_id)
        await CommandJoin.finish(Message(f"[CQ:at,qq={str(int(user_id))}] 已加入游戏"))


@CommandExit.handle()
async def _(event: MessageEvent):
    if not isinstance(event, GroupMessageEvent):
        await CommandExit.finish("请在群聊中使用该指令。")
    group_id: str = str(event.group_id)
    async with _room_manager.lock(group_id):
        if group_id not in _room_manager.rooms or not _room_manager.rooms[group_id]:
            await CommandExit.finish("没有正在进行的游戏. ")
        room = _room_manager.rooms[group_id]
        if room.state != "lobby":
            await CommandExit.finish("游戏已开始，无法中途退出。")
        user_id: str = event.get_user_id()
        await room.remove_player(user_id)
        await CommandExit.finish(Message(f"[CQ:at,qq={str(int(user_id))}] 已离开游戏"))


@CommandAddrole.handle()
async def _(event: MessageEvent, args: Message = CommandArg()):
    if not isinstance(event, GroupMessageEvent):
        await CommandAddrole.finish("请在群聊中使用该指令。")
    group_id: str = str(event.group_id)
    async with _room_manager.lock(group_id):
        if group_id not in _room_manager.rooms or not _room_manager.rooms[group_id]:
            await CommandAddrole.finish("没有正在进行的游戏. ")
        room = _room_manager.rooms[group_id]
        if room.state != "lobby":
            await CommandAddrole.finish("游戏已开始，无法修改角色配置。")
        role_list = args.extract_plain_text().split(" ")
        await room.add_character(role_list)


@CommandRmrole.handle()
async def _(event: MessageEvent, args: Message = CommandArg()):
    if not isinstance(event, GroupMessageEvent):
        await CommandRmrole.finish("请在群聊中使用该指令。")
    group_id: str = str(event.group_id)
    async with _room_manager.lock(group_id):
        if group_id not in _room_manager.rooms or not _room_manager.rooms[group_id]:
            await CommandRmrole.finish("没有正在进行的游戏. ")
        room = _room_manager.rooms[group_id]
        if room.state != "lobby":
            await CommandRmrole.finish("游戏已开始，无法修改角色配置。")
        role_list: list[str] = args.extract_plain_text().split(" ")
        await room.remove_character(role_list)


@CommandShowroles.handle()
async def _(event: MessageEvent):
    if not isinstance(event, GroupMessageEvent):
        await CommandShowroles.finish("请在群聊中使用该指令。")
    group_id: str = str(event.group_id)
    async with _room_manager.lock(group_id):
        if group_id not in _room_manager.rooms or not _room_manager.rooms[group_id]:
            await CommandShowroles.finish("没有正在进行的游戏. ")
        room = _room_manager.rooms[group_id]
        if not room.character_enabled:
            await CommandShowroles.finish(
                "当前未添加任何角色（未配置将默认补足为村民）。"
            )
        lines: list[str] = []
        for role_cls, count in room.character_enabled.items():
            name = getattr(role_cls, "name", role_cls.__name__)
            lines.append(f"{name}: {count}")
        await CommandShowroles.finish("\n".join(lines))


@CommandAutoroles.handle()
async def _(event: MessageEvent):
    if not isinstance(event, GroupMessageEvent):
        await CommandAutoroles.finish("请在群聊中使用该指令。")
    group_id: str = str(event.group_id)
    async with _room_manager.lock(group_id):
        if group_id not in _room_manager.rooms or not _room_manager.rooms[group_id]:
            await CommandAutoroles.finish("没有正在进行的游戏. ")
        room = _room_manager.rooms[group_id]
        if room.state != "lobby":
            await CommandAutoroles.finish("游戏已开始，无法修改角色配置。")
        n = len(room.player_list)
        if n < 4:
            await CommandAutoroles.finish("玩家人数不足（至少 4 人）。")

        # A simple common setup: 1 seer; wolves grow with player count; rest are villagers.
        if n <= 5:
            wolves = 1
        elif n <= 8:
            wolves = 2
        elif n <= 11:
            wolves = 3
        else:
            wolves = 4

        room.character_enabled.clear()
        wolf_cls = get_character_class_by_role_id("wolf")
        seer_cls = get_character_class_by_role_id("seer")
        person_cls = get_character_class_by_role_id("person")
        if not wolf_cls or not seer_cls or not person_cls:
            await CommandAutoroles.finish(
                "角色加载异常：缺少狼人/预言家/村民角色定义。"
            )
        room.character_enabled[wolf_cls] = wolves
        room.character_enabled[seer_cls] = 1
        room.character_enabled[person_cls] = n - wolves - 1
        # if len(role_pool) < len(self.player_list):
        #     role_pool.extend(
        #         [CharacterPerson] * (len(self.player_list) - len(role_pool))
        #     )
        await CommandAutoroles.finish(
            f"已自动配置角色：狼人 x{wolves}，预言家 x1，其余为村民。"
        )


@CommandStart.handle()
async def _(event: MessageEvent):
    if not isinstance(event, GroupMessageEvent):
        await CommandStart.finish("请在群聊中使用该指令。")
    group_id: str = str(event.group_id)
    async with _room_manager.lock(group_id):
        if group_id not in _room_manager.rooms or not _room_manager.rooms[group_id]:
            await CommandStart.finish("没有正在进行的游戏. ")
        await _room_manager.rooms[group_id].start_game()


@CommandSkill.handle()
async def _(event: MessageEvent, args: Message = CommandArg()):
    user_id = event.get_user_id()

    raw_tokens = [x for x in args.extract_plain_text().strip().split() if x]
    hinted_group_id, arg_list, err = _extract_group_id_hint(raw_tokens)
    if err:
        await CommandSkill.finish(err)

    group_id: str | None = None
    if isinstance(event, GroupMessageEvent):
        group_id = str(event.group_id)
        if hinted_group_id and hinted_group_id != group_id:
            await CommandSkill.finish(
                "请在对应群聊中使用该指令（群号与当前群不一致）。"
            )
    else:
        if hinted_group_id:
            group_id = hinted_group_id
        else:
            group_id, _, err = _resolve_room_for_private_user(user_id)
            if err or not group_id:
                await CommandSkill.finish(err or "没有正在进行的游戏. ")
        if group_id and user_id in ban_user.get(group_id, set()):
            await CommandSkill.finish("你已被该群拉黑，无法使用该指令。")

    if not group_id:
        await CommandSkill.finish("没有正在进行的游戏. ")

    async with _room_manager.lock(group_id):
        room = _room_manager.rooms.get(group_id)
        if not room:
            if isinstance(event, GroupMessageEvent):
                await CommandSkill.finish("没有正在进行的游戏. ")
            await CommandSkill.finish(f"群聊 {group_id} 没有正在进行的游戏。")
        if room.state == "ended":
            await CommandSkill.finish("该群的游戏已结束，请先 `wft.init`。")

        if not isinstance(event, GroupMessageEvent) and user_id not in room.id_2_player:
            await CommandSkill.finish("你不在该群的游戏中。")

        player = room.id_2_player.get(user_id)
        if not player or not player.alive:
            await CommandSkill.finish("你不在游戏中，或已死亡。")
        if not player.role:
            await CommandSkill.finish("游戏还未开始（尚未分配身份）。")
        if not arg_list:
            await CommandSkill.finish(
                "用法：`wft.skill <动作> [参数]`（私聊可用 `-g <群号>` 指定群）"
            )
        await room.events_system.event_skill.active(room, user_id, arg_list)


@CommandVote.handle()
async def _(event: MessageEvent, args: Message = CommandArg()):
    if not isinstance(event, GroupMessageEvent):
        await CommandVote.finish("请在群聊中使用该指令。")
    group_id: str = str(event.group_id)
    async with _room_manager.lock(group_id):
        if group_id not in _room_manager.rooms or not _room_manager.rooms[group_id]:
            await CommandVote.finish("没有正在进行的游戏. ")
        room = _room_manager.rooms[group_id]
        text = args.extract_plain_text().strip()
        if not text.isdigit():
            await CommandVote.finish("用法：`wft.vote <编号>`（编号需要是数字）")
        await room.events_system.event_vote.active(room, event.get_user_id(), [text])


@CommandSkip.handle()
async def _(event: MessageEvent, args: Message = CommandArg()):
    user_id = event.get_user_id()

    raw_tokens = [x for x in args.extract_plain_text().strip().split() if x]
    hinted_group_id, _, err = _extract_group_id_hint(raw_tokens)
    if err:
        await CommandSkip.finish("用法：`wft.skip -g <群号>`")

    group_id: str | None = None
    if isinstance(event, GroupMessageEvent):
        group_id = str(event.group_id)
        if hinted_group_id and hinted_group_id != group_id:
            await CommandSkip.finish("请在对应群聊中使用该指令（群号与当前群不一致）。")
    else:
        if hinted_group_id:
            group_id = hinted_group_id
        else:
            group_id, _, err = _resolve_room_for_private_user(user_id)
            if err or not group_id:
                await CommandSkip.finish(err or "没有正在进行的游戏. ")
        if group_id and user_id in ban_user.get(group_id, set()):
            await CommandSkip.finish("你已被该群拉黑，无法使用该指令。")

    if not group_id:
        await CommandSkip.finish("没有正在进行的游戏. ")

    async with _room_manager.lock(group_id):
        room = _room_manager.rooms.get(group_id)
        if not room:
            if isinstance(event, GroupMessageEvent):
                await CommandSkip.finish("没有正在进行的游戏. ")
            await CommandSkip.finish(f"群聊 {group_id} 没有正在进行的游戏。")
        if room.state == "ended":
            await CommandSkip.finish("该群的游戏已结束。")
        if not isinstance(event, GroupMessageEvent):
            if user_id not in room.id_2_player:
                await CommandSkip.finish("你不在该群的游戏中。")
            if room.state != "night":
                await CommandSkip.finish("当前阶段请在群聊中使用该指令。")

        await room.events_system.event_skip.active(room, user_id, [])
