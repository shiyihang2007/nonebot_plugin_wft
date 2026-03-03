from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from game.character_person import CharacterPerson
from game.character_seer import CharacterSeer
from game.character_wolf import CharacterWolf


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_night_start__alive_locks_and_prompts(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    seer = CharacterSeer(room, players[0])
    players[0].role = seer

    await seer.on_night_start(room, None, [])

    assert seer._night_done is False
    assert room.events_system.event_night_end.lock_count >= 1
    assert "你是预言家" in fake_io["private_messages"][-1][1]


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_night_start__dead_user_ignored(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    seer = CharacterSeer(room, players[0])
    players[0].role = seer
    players[0].alive = False
    lock_before = room.events_system.event_night_end.lock_count

    await seer.on_night_start(room, None, [])

    assert room.events_system.event_night_end.lock_count == lock_before


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skill__precondition_guards(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    seer = CharacterSeer(room, players[0])
    players[0].role = seer

    room.state = "night"
    await seer.on_skill(room, "2001", ["check", "1"])
    assert seer._night_done is False

    room.state = "speech"
    await seer.on_skill(room, "1001", ["check", "1"])
    assert seer._night_done is False

    room.state = "night"
    await seer.on_skill(room, "1001", [])
    assert seer._night_done is False

    await seer.on_skill(room, "1001", ["bad", "1"])
    assert seer._night_done is False


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skill__repeat_operation_rejected(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    seer = CharacterSeer(room, players[0])
    players[0].role = seer
    room.state = "night"
    seer._night_done = True

    await seer.on_skill(room, "1001", ["check", "1"])

    assert "今晚已经完成" in fake_io["private_messages"][-1][1]


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skill__invalid_seat_or_check_failure_send_error(
    room_factory, players_factory, fake_io
) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    seer = CharacterSeer(room, players[0])
    players[0].role = seer
    room.state = "night"

    await seer.on_skill(room, "1001", ["check", "x"])
    assert "编号需要是数字" in fake_io["private_messages"][-1][1]

    await seer.on_skill(room, "1001", ["check", "9"])
    assert "目标编号无效" in fake_io["private_messages"][-1][1]


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skill__valid_check_triggers_event_and_unlock(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 2, 1001)
    seer = CharacterSeer(room, players[0])
    players[0].role = seer
    players[1].role = CharacterPerson(room, players[1])
    room.state = "night"

    seer_event = room.events_system.get_or_create_event("seer_check")
    seer_event.active = AsyncMock()
    room.events_system.event_night_end.unlock = AsyncMock()

    await seer.on_skill(room, "1001", ["check", "2"])

    assert seer._night_done is True
    seer_event.active.assert_awaited_once()
    room.events_system.event_night_end.unlock.assert_awaited_once_with(room, "1001", [])


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skip__set_done_and_unlock(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    seer = CharacterSeer(room, players[0])
    players[0].role = seer
    room.state = "night"
    room.events_system.event_night_end.unlock = AsyncMock()

    await seer.on_skip(room, "1001", [])

    assert seer._night_done is True
    assert "放弃本夜查验" in fake_io["private_messages"][-1][1]
    room.events_system.event_night_end.unlock.assert_awaited_once_with(room, "1001", [])


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skip__wrong_user_or_wrong_stage_or_done_ignored(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    seer = CharacterSeer(room, players[0])
    players[0].role = seer

    room.state = "night"
    await seer.on_skip(room, "2001", [])
    assert seer._night_done is False

    room.state = "speech"
    await seer.on_skip(room, "1001", [])
    assert seer._night_done is False

    room.state = "night"
    seer._night_done = True
    await seer.on_skip(room, "1001", [])
    assert seer._night_done is True


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_seer_check_event__empty_or_text_result(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    seer = CharacterSeer(room, players[0])
    players[0].role = seer

    await seer.on_seer_check_event(room, "1001", [])
    assert "用法" in fake_io["private_messages"][-1][1]

    await seer.on_seer_check_event(room, "1001", ["2", "查验结果: 2号 是 好人。"])
    assert "查验结果" in fake_io["private_messages"][-1][1]


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_seer_check_event__not_self_or_non_digit_branch(
    room_factory, players_factory, fake_io
) -> None:
    room = room_factory()
    players = players_factory(room, 2, 1001)
    seer = CharacterSeer(room, players[0])
    players[0].role = seer
    players[1].role = CharacterPerson(room, players[1])

    await seer.on_seer_check_event(room, "2001", ["2"])
    assert fake_io["private_messages"] == []

    await seer.on_seer_check_event(room, "1001", ["x"])
    assert "编号需要是数字" in fake_io["private_messages"][-1][1]

    await seer.on_seer_check_event(room, "1001", ["2"])
    assert "查验结果" in fake_io["private_messages"][-1][1]


@pytest.mark.character
@pytest.mark.parametrize(
    ("seat", "alive", "camp", "expected_ok", "expected_contains"),
    [
        (99, True, "good", False, "目标编号无效"),
        (2, False, "good", False, "目标已死亡"),
        (2, True, "wolf", True, "狼人"),
        (2, True, "good", True, "好人"),
    ],
)
def test_check__branches(room_factory, players_factory, seat, alive, camp, expected_ok, expected_contains) -> None:
    room = room_factory()
    players = players_factory(room, 2, 1001)
    seer = CharacterSeer(room, players[0])
    players[0].role = seer

    if seat == 2:
        players[1].alive = alive
        if camp == "wolf":
            players[1].role = CharacterWolf(room, players[1])
        else:
            players[1].role = CharacterPerson(room, players[1])

    ok, result = seer._check(seat)
    assert ok is expected_ok
    assert expected_contains in result


@pytest.mark.character
def test_check__role_missing_returns_unknown(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 2, 1001)
    seer = CharacterSeer(room, players[0])
    players[0].role = seer
    players[1].role = None

    ok, result = seer._check(2)
    assert ok is False
    assert "身份未知" in result
