from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from game.character_base import CharacterBase
from game.room import Room


class DummyWolfRole(CharacterBase):
    role_id = "test_wolf_role"
    name = "测试狼"
    camp = "wolf"
    aliases: list[str] = []


class DummyGoodRole(CharacterBase):
    role_id = "test_good_role"
    name = "测试好人"
    camp = "good"
    aliases: list[str] = []


@pytest.mark.unit
def test_register_core_event_listeners__binds_handlers(room_factory) -> None:
    room = room_factory()
    room._register_core_event_listeners()

    assert room.events_system.event_game_start._listeners
    assert room.events_system.event_night_start._listeners
    assert room.events_system.event_vote._listeners
    assert room.events_system.event_day_end._listeners


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_game__reject_when_not_lobby(room_factory, fake_io, players_factory) -> None:
    room = room_factory()
    players_factory(room, 4, 1001)
    room.state = "night"

    await room.start_game()

    assert "无法重复开始" in fake_io["group_messages"][-1][1]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_game__reject_when_player_not_enough(room_factory, fake_io, players_factory) -> None:
    room = room_factory()
    players_factory(room, 3, 1001)

    await room.start_game()

    assert "玩家人数不足" in fake_io["group_messages"][-1][1]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_game__debug_mode_allows_less_players(room_factory, fake_io, players_factory, monkeypatch) -> None:
    room = room_factory()
    players_factory(room, 3, 1001)
    room.settings.debug = True
    room.character_enabled = {DummyWolfRole: 1, DummyGoodRole: 2}
    monkeypatch.setattr("game.room.random.shuffle", lambda x: None)

    await room.start_game()

    assert any("警告：调试模式已启用" in msg for _, msg in fake_io["group_messages"])


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_game__reject_when_role_count_exceeds_players(
    room_factory, fake_io, players_factory
) -> None:
    room = room_factory()
    players_factory(room, 4, 1001)
    room.character_enabled = {DummyWolfRole: 3, DummyGoodRole: 2}

    await room.start_game()

    assert "超过玩家人数" in fake_io["group_messages"][-1][1]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_game__reject_when_no_wolf(room_factory, fake_io, players_factory) -> None:
    room = room_factory()
    players_factory(room, 4, 1001)
    room.character_enabled = {DummyGoodRole: 4}

    await room.start_game()

    assert "至少需要 1 个狼人角色" in fake_io["group_messages"][-1][1]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_game__skip_non_positive_role_count(room_factory, fake_io, players_factory) -> None:
    room = room_factory()
    players_factory(room, 4, 1001)
    room.character_enabled = {DummyWolfRole: 0, DummyGoodRole: 4}

    await room.start_game()

    assert "至少需要 1 个狼人角色" in fake_io["group_messages"][-1][1]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_game__success_assigns_roles_and_sends_cards(
    room_factory, fake_io, players_factory, monkeypatch
) -> None:
    room = room_factory()
    players = players_factory(room, 4, 1001)
    room.character_enabled = {DummyWolfRole: 1, DummyGoodRole: 3}
    monkeypatch.setattr("game.room.random.shuffle", lambda x: None)

    await room.start_game()

    assert all(p.role is not None for p in players)
    assert any("游戏开始" in msg for _, msg in fake_io["group_messages"])
    assert len(fake_io["private_messages"]) == 4
    assert room.state != "lobby"


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_start_game__players_without_role_are_skipped_in_private_card(
    room_factory, fake_io, players_factory, monkeypatch
) -> None:
    room = room_factory()
    players_factory(room, 4, 1001)
    room.character_enabled = {DummyWolfRole: 1}
    monkeypatch.setattr("game.room.random.shuffle", lambda x: None)

    await room.start_game()

    assert len(fake_io["private_messages"]) == 1


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_game_start__bridge_to_night_start(room_factory) -> None:
    room = room_factory()
    room.events_system.event_night_start.lock = MagicMock()
    room.events_system.event_night_start.unlock = AsyncMock()

    await room._on_game_start(room, None, [])

    room.events_system.event_night_start.lock.assert_called_once()
    room.events_system.event_night_start.unlock.assert_awaited_once_with(room, None, [])


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_night_start__reset_state_and_broadcast(room_factory, fake_io) -> None:
    room = room_factory()
    room.pending_death_records = {"1001": "x"}

    await room._on_night_start(room, None, [])

    assert room.state == "night"
    assert room.pending_death_records == {}
    assert fake_io["group_messages"][-1][1] == "天黑请闭眼。"


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_night_start_kick_night_end__lock_then_unlock(room_factory) -> None:
    room = room_factory()
    room.events_system.event_night_end.lock = MagicMock()
    room.events_system.event_night_end.unlock = AsyncMock()

    await room._on_night_start_kick_night_end(room, None, [])

    room.events_system.event_night_end.lock.assert_called_once()
    room.events_system.event_night_end.unlock.assert_awaited_once_with(room, None, [])


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_night_end__wrong_state_logs_warning(room_factory, caplog) -> None:
    room = room_factory()
    room.state = "speech"

    with caplog.at_level("WARNING"):
        await room._on_night_end(room, None, [])

    assert "不正确的阶段" in caplog.text


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_night_end__no_victim_unlock_day_start(room_factory, fake_io) -> None:
    room = room_factory()
    room.state = "night"
    room.pending_death_records = {}
    room.events_system.event_day_start.lock = MagicMock()
    room.events_system.event_day_start.unlock = AsyncMock()

    await room._on_night_end(room, None, [])

    assert "平安夜" in fake_io["group_messages"][-1][1]
    room.events_system.event_day_start.lock.assert_called_once()
    room.events_system.event_day_start.unlock.assert_awaited_once_with(room, None, [])


@pytest.mark.spec_expected
@pytest.mark.xfail(
    reason="WFT-TEST-001: pending_death_records 应按 dict.items() 遍历",
    strict=False,
)
@pytest.mark.asyncio
async def test_on_night_end__spec_should_dispatch_person_killed_for_each_pending_record(
    room_factory,
) -> None:
    room = room_factory()
    room.state = "night"
    room.pending_death_records = {"1001": "被狼刀了"}
    room.id_2_player["1001"] = MagicMock(seat=1)
    room.events_system.event_person_killed.active = AsyncMock()
    room.events_system.event_day_start.lock = MagicMock()
    room.events_system.event_day_start.unlock = AsyncMock()

    await room._on_night_end(room, None, [])

    room.events_system.event_person_killed.active.assert_awaited_once_with(
        room, "1001", ["被狼刀了", "day_start"]
    )


@pytest.mark.known_issue
@pytest.mark.asyncio
async def test_on_night_end__current_behavior_raises_when_pending_records_is_dict(
    room_factory,
) -> None:
    room = room_factory()
    room.state = "night"
    room.pending_death_records = {"1001": "被狼刀了"}
    room.id_2_player["1001"] = MagicMock(seat=1)

    with pytest.raises(ValueError):
        await room._on_night_end(room, None, [])


@pytest.mark.known_issue
@pytest.mark.asyncio
async def test_on_night_end__current_weird_iteration_with_two_char_key(room_factory, fake_io) -> None:
    room = room_factory()
    room.state = "night"
    room.pending_death_records = {"ab": "被狼刀了"}
    room.id_2_player["a"] = MagicMock(seat=1)
    room.events_system.event_person_killed.active = AsyncMock()
    room.events_system.event_day_start.lock = MagicMock()
    room.events_system.event_day_start.unlock = AsyncMock()

    await room._on_night_end(room, None, [])

    assert "昨晚 1号 死亡" in fake_io["group_messages"][-1][1]
    room.events_system.event_person_killed.active.assert_awaited_once_with(
        room, "a", ["b", "day_start"]
    )
    room.events_system.event_day_start.unlock.assert_not_awaited()


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_day_start__winner_direct_to_game_end(room_factory) -> None:
    room = room_factory()
    room.check_winner = MagicMock(return_value="good")
    room.events_system.event_game_end.active = AsyncMock()

    await room._on_day_start(room, None, [])

    room.events_system.event_game_end.active.assert_awaited_once_with(room, None, ["good"])


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_day_start__speech_order_ascending(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players_factory(room, 3, 1001)
    room.check_winner = MagicMock(return_value=None)

    await room._on_day_start(room, None, [])

    assert room.state == "speech"
    assert room.day_count == 1
    assert room.day_speech_order_user_ids == ["1001", "1002", "1003"]
    assert "从小到大" in fake_io["group_messages"][-1][1]


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_day_start__speech_order_descending(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players_factory(room, 3, 1001)
    room.check_winner = MagicMock(return_value=None)
    room.day_count = 1

    await room._on_day_start(room, None, [])

    assert room.day_count == 2
    assert room.day_speech_order_user_ids == ["1003", "1002", "1001"]
    assert "从大到小" in fake_io["group_messages"][-1][1]


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_day_start__no_alive_players_end_game(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 2, 1001)
    for p in players:
        p.alive = False
    room.check_winner = MagicMock(return_value=None)
    room.events_system.event_game_end.active = AsyncMock()

    await room._on_day_start(room, None, [])

    room.events_system.event_game_end.active.assert_awaited_once_with(room, None, ["good"])


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_skip_input_speech__wrong_user_gets_prompt(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players_factory(room, 2, 1001)
    room.state = "speech"
    room.day_speech_order_user_ids = ["1001", "1002"]
    room.day_speech_index = 0

    await room._on_skip_input_speech(room, "1002", [])

    assert "还没轮到你发言" in fake_io["group_messages"][-1][1]


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_skip_input_speech__precondition_guards(room_factory, players_factory) -> None:
    room = room_factory()
    players_factory(room, 2, 1001)
    room.day_speech_order_user_ids = ["1001", "1002"]

    room.state = "vote"
    await room._on_skip_input_speech(room, "1001", [])
    assert room.day_speech_index == 0

    room.state = "speech"
    await room._on_skip_input_speech(room, None, [])
    assert room.day_speech_index == 0

    room.day_speech_index = 10
    await room._on_skip_input_speech(room, "1001", [])
    assert room.day_speech_index == 10


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_skip_input_speech__advance_to_next_player(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players_factory(room, 2, 1001)
    room.state = "speech"
    room.day_speech_order_user_ids = ["1001", "1002"]
    room.day_speech_index = 0

    await room._on_skip_input_speech(room, "1001", [])

    assert room.day_speech_index == 1
    assert "请 2号 发言" in fake_io["group_messages"][-1][1]


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_skip_input_speech__advance_and_start_vote_at_end(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players_factory(room, 1, 1001)
    room.state = "speech"
    room.day_speech_order_user_ids = ["1001"]
    room.day_speech_index = 0
    room.events_system.event_vote_start.active = AsyncMock()

    await room._on_skip_input_speech(room, "1001", [])

    assert "发言结束" in fake_io["group_messages"][-1][1]
    room.events_system.event_vote_start.active.assert_awaited_once_with(room, None, [])


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_vote_start__setup_vote_phase(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players_factory(room, 3, 1001)
    room.events_system.event_vote_end.lock = MagicMock()

    await room._on_vote_start(room, None, [])

    assert room.state == "vote"
    assert room.vote_pending_user_ids == {"1001", "1002", "1003"}
    assert room.events_system.event_vote_end.lock.call_count == 3
    assert "投票阶段开始" in fake_io["group_messages"][-1][1]


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_vote_input__valid_vote_unlocks_only_first_time(room_factory, players_factory) -> None:
    room = room_factory()
    players_factory(room, 2, 1001)
    room.state = "vote"
    room.vote_pending_user_ids = {"1001", "1002"}
    room.events_system.event_vote_end.unlock = AsyncMock()

    await room._on_vote_input(room, "1001", ["2"])
    await room._on_vote_input(room, "1001", ["1"])

    assert room.votes["1001"] == "1001"
    room.events_system.event_vote_end.unlock.assert_awaited_once_with(room, "1001", [])


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_vote_input__precondition_guards(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 2, 1001)
    room.events_system.event_vote_end.unlock = AsyncMock()

    room.state = "speech"
    await room._on_vote_input(room, "1001", ["2"])
    assert room.votes == {}

    room.state = "vote"
    await room._on_vote_input(room, None, ["2"])
    assert room.votes == {}

    players[0].alive = False
    await room._on_vote_input(room, "1001", ["2"])
    assert room.votes == {}
    players[0].alive = True

    await room._on_vote_input(room, "1001", [])
    assert room.votes == {}

    await room._on_vote_input(room, "1001", ["x"])
    assert room.votes == {}


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_vote_input__target_invalid_or_dead_ignored(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 2, 1001)
    room.state = "vote"
    room.vote_pending_user_ids = {"1001"}
    room.events_system.event_vote_end.unlock = AsyncMock()

    await room._on_vote_input(room, "1001", ["9"])
    assert room.votes == {}

    players[1].alive = False
    await room._on_vote_input(room, "1001", ["2"])
    assert room.votes == {}


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_skip_input_vote__skip_unlocks(room_factory, players_factory) -> None:
    room = room_factory()
    players_factory(room, 2, 1001)
    room.state = "vote"
    room.vote_pending_user_ids = {"1001"}
    room.events_system.event_vote_end.unlock = AsyncMock()

    await room._on_skip_input_vote(room, "1001", [])

    assert room.votes["1001"] is None
    room.events_system.event_vote_end.unlock.assert_awaited_once_with(room, "1001", [])


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_skip_input_vote__precondition_guards_and_repeat_skip(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 2, 1001)
    room.events_system.event_vote_end.unlock = AsyncMock()

    room.state = "speech"
    await room._on_skip_input_vote(room, "1001", [])
    assert room.votes == {}

    room.state = "vote"
    await room._on_skip_input_vote(room, None, [])
    assert room.votes == {}

    players[0].alive = False
    await room._on_skip_input_vote(room, "1001", [])
    assert room.votes == {}
    players[0].alive = True

    room.vote_pending_user_ids = {"1001"}
    await room._on_skip_input_vote(room, "1001", [])
    await room._on_skip_input_vote(room, "1001", [])
    room.events_system.event_vote_end.unlock.assert_awaited_once_with(room, "1001", [])


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_vote_end__wrong_state_logs_warning(room_factory, caplog) -> None:
    room = room_factory()
    room.state = "speech"

    with caplog.at_level("WARNING"):
        await room._on_vote_end(room, None, [])

    assert "不正确的阶段" in caplog.text


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_vote_end__no_votes_goes_day_end(room_factory, fake_io) -> None:
    room = room_factory()
    room.state = "vote"
    room.votes = {}
    room.events_system.event_day_end.active = AsyncMock()

    await room._on_vote_end(room, None, [])

    assert "无票" in fake_io["group_messages"][-1][1]
    room.events_system.event_day_end.active.assert_awaited_once_with(room, None, [])


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_vote_end__tie_goes_day_end(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players_factory(room, 3, 1001)
    room.state = "vote"
    room.votes = {"1001": "1002", "1002": "1001"}
    room.events_system.event_day_end.active = AsyncMock()

    await room._on_vote_end(room, None, [])

    assert "票数相同" in fake_io["group_messages"][-1][1]
    room.events_system.event_day_end.active.assert_awaited_once_with(room, None, [])


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_vote_end__valid_target_dispatch_killed_and_unlock_day_end(
    room_factory, players_factory, fake_io
) -> None:
    room = room_factory()
    players_factory(room, 3, 1001)
    room.state = "vote"
    room.votes = {"1001": "1002", "1003": "1002"}
    room.events_system.event_day_end.lock = MagicMock()
    room.events_system.event_day_end.unlock = AsyncMock()
    room.events_system.event_person_killed.active = AsyncMock()

    await room._on_vote_end(room, None, [])

    assert "被放逐" in fake_io["group_messages"][-1][1]
    room.events_system.event_person_killed.active.assert_awaited_once_with(
        room, "1002", ["白天投票放逐", "day_end"]
    )
    room.events_system.event_day_end.unlock.assert_awaited_once_with(room, None, [])


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_vote_end__invalid_target_broadcasts_and_unlocks(room_factory, fake_io) -> None:
    room = room_factory()
    room.state = "vote"
    room.votes = {"1001": "9999"}
    room.events_system.event_day_end.lock = MagicMock()
    room.events_system.event_day_end.unlock = AsyncMock()
    room.events_system.event_person_killed.active = AsyncMock()

    await room._on_vote_end(room, None, [])

    assert "目标无效" in fake_io["group_messages"][-1][1]
    room.events_system.event_person_killed.active.assert_not_awaited()
    room.events_system.event_day_end.unlock.assert_awaited_once_with(room, None, [])


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_day_end__winner_to_game_end(room_factory) -> None:
    room = room_factory()
    room.check_winner = MagicMock(return_value="wolf")
    room.events_system.event_game_end.active = AsyncMock()

    await room._on_day_end(room, None, [])

    room.events_system.event_game_end.active.assert_awaited_once_with(room, None, ["wolf"])


@pytest.mark.room_flow
@pytest.mark.asyncio
async def test_on_day_end__no_winner_to_night_start(room_factory) -> None:
    room = room_factory()
    room.check_winner = MagicMock(return_value=None)
    room.events_system.event_night_start.active = AsyncMock()

    await room._on_day_end(room, None, [])

    room.events_system.event_night_start.active.assert_awaited_once_with(room, None, [])


@pytest.mark.room_flow
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("winner", "expected_text"),
    [
        ("good", "好人胜利"),
        ("wolf", "狼人胜利"),
        (None, "游戏结束。"),
    ],
)
async def test_on_game_end__broadcasts_result(room_factory, fake_io, winner, expected_text) -> None:
    room = room_factory()

    args = [] if winner is None else [winner]
    await room._on_game_end(room, None, args)

    assert expected_text in fake_io["group_messages"][-1][1]
    assert room.state == "ended"


@pytest.mark.room_flow
def test_check_winner__three_states(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 3, 1001)

    players[0].role = DummyWolfRole(room, players[0])
    players[1].role = DummyGoodRole(room, players[1])
    players[2].role = DummyGoodRole(room, players[2])
    assert room.check_winner() is None

    players[0].alive = False
    assert room.check_winner() == "good"

    players[0].alive = True
    players[1].alive = False
    players[2].alive = False
    assert room.check_winner() == "wolf"
