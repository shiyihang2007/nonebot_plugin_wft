from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from game.character_guard import CharacterGuard
from game.character_person import CharacterPerson


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_night_start__alive_locks_and_prompt(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    guard = CharacterGuard(room, players[0])
    players[0].role = guard

    await guard.on_night_start(room, None, [])

    assert guard._guard_user_id is None
    assert guard._night_responded is False
    assert room.events_system.event_night_end.lock_count >= 1
    assert "你是守卫" in fake_io["private_messages"][-1][1]


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_night_start__dead_user_ignored(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    guard = CharacterGuard(room, players[0])
    players[0].role = guard
    players[0].alive = False
    lock_before = room.events_system.event_night_end.lock_count

    await guard.on_night_start(room, None, [])

    assert room.events_system.event_night_end.lock_count == lock_before


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skill__cannot_guard_same_target_twice(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 2, 1001)
    guard = CharacterGuard(room, players[0])
    players[0].role = guard
    players[1].role = CharacterPerson(room, players[1])
    room.state = "night"
    guard._last_guard_user_id = "1002"

    await guard.on_skill(room, "1001", ["guard", "2"])

    assert "不能连续两晚" in fake_io["private_messages"][-1][1]


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skill__basic_preconditions(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    guard = CharacterGuard(room, players[0])
    players[0].role = guard

    await guard.on_skill(room, "2001", ["guard", "1"])
    assert fake_io["private_messages"] == []

    players[0].alive = False
    await guard.on_skill(room, "1001", ["guard", "1"])
    assert fake_io["private_messages"] == []
    players[0].alive = True

    room.state = "speech"
    await guard.on_skill(room, "1001", ["guard", "1"])
    assert fake_io["private_messages"] == []

    room.state = "night"
    await guard.on_skill(room, "1001", [])
    assert "用法" in fake_io["private_messages"][-1][1]

    await guard.on_skill(room, "1001", ["bad", "1"])
    assert "用法" in fake_io["private_messages"][-1][1]


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skill__valid_guard_unlocks_once(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 2, 1001)
    guard = CharacterGuard(room, players[0])
    players[0].role = guard
    players[1].role = CharacterPerson(room, players[1])
    room.state = "night"
    room.events_system.event_night_end.unlock = AsyncMock()

    await guard.on_skill(room, "1001", ["guard", "2"])
    await guard.on_skill(room, "1001", ["guard", "2"])

    assert guard._guard_user_id == "1002"
    assert "守护 2号" in fake_io["private_messages"][-1][1]
    room.events_system.event_night_end.unlock.assert_awaited_once_with(room, "1001", [])


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skill__invalid_target_or_dead_target(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 2, 1001)
    guard = CharacterGuard(room, players[0])
    players[0].role = guard
    players[1].role = CharacterPerson(room, players[1])
    room.state = "night"

    await guard.on_skill(room, "1001", ["guard", "99"])
    assert "目标编号无效" in fake_io["private_messages"][-1][1]

    players[1].alive = False
    await guard.on_skill(room, "1001", ["guard", "2"])
    assert "目标已死亡" in fake_io["private_messages"][-1][1]


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skip__unlock_once(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    guard = CharacterGuard(room, players[0])
    players[0].role = guard
    room.state = "night"
    room.events_system.event_night_end.unlock = AsyncMock()

    await guard.on_skip(room, "1001", [])

    assert guard._guard_user_id is None
    assert "放弃本夜守护" in fake_io["private_messages"][-1][1]
    room.events_system.event_night_end.unlock.assert_awaited_once_with(room, "1001", [])


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skip__wrong_user_or_stage_ignored(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    guard = CharacterGuard(room, players[0])
    players[0].role = guard

    room.state = "night"
    await guard.on_skip(room, "2001", [])
    assert guard._night_responded is False

    room.state = "speech"
    await guard.on_skip(room, "1001", [])
    assert guard._night_responded is False


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_night_end__removes_only_wolf_kill_record(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    guard = CharacterGuard(room, players[0])
    players[0].role = guard
    guard._guard_user_id = "1002"

    room.pending_death_records = {
        "1002": "被狼刀了",
        "1003": "被毒死了",
    }

    await guard.on_night_end(room, None, [])

    assert guard._last_guard_user_id == "1002"
    assert "1002" not in room.pending_death_records
    assert room.pending_death_records["1003"] == "被毒死了"


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_night_end__no_match_or_not_wolf_kill_do_nothing(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    guard = CharacterGuard(room, players[0])
    players[0].role = guard

    guard._guard_user_id = "1009"
    room.pending_death_records = {"1002": "被毒死了"}
    await guard.on_night_end(room, None, [])
    assert room.pending_death_records == {"1002": "被毒死了"}

    guard._guard_user_id = "1002"
    await guard.on_night_end(room, None, [])
    assert room.pending_death_records == {"1002": "被毒死了"}
