from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from game.character_hunter import CharacterHunter
from game.character_person import CharacterPerson


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_killed__poisoned_cannot_shoot(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    hunter = CharacterHunter(room, players[0])
    players[0].role = hunter

    await hunter.on_killed(room, "1001", ["被毒死了", "day_end"])

    assert hunter.skill_available is False
    assert "无法使用猎枪" in fake_io["private_messages"][-1][1]


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_killed__other_user_ignored(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    hunter = CharacterHunter(room, players[0])
    players[0].role = hunter

    await hunter.on_killed(room, "2001", ["白天放逐", "day_end"])

    assert hunter.skill_available is False


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_killed__normal_death_locks_blocked_event(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    hunter = CharacterHunter(room, players[0])
    players[0].role = hunter

    initial_lock = room.events_system.event_day_end.lock_count
    await hunter.on_killed(room, "1001", ["白天放逐", "day_end"])

    assert hunter.skill_available is True
    assert room.events_system.event_day_end.lock_count == initial_lock + 1
    assert "你是猎人" in fake_io["private_messages"][-1][1]


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skill__shoot_valid_target_and_unlock(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 2, 1001)
    hunter = CharacterHunter(room, players[0])
    players[0].role = hunter
    players[1].role = CharacterPerson(room, players[1])

    hunter.skill_available = True
    hunter.blocked_event = AsyncMock()
    hunter.blocked_event.name = "day_end"
    room.events_system.event_person_killed.active = AsyncMock()

    await hunter.on_skill(room, "1001", ["shoot", "2"])

    assert hunter.skill_available is False
    room.events_system.event_person_killed.active.assert_awaited_once_with(
        hunter,
        "1002",
        ["被枪杀", "day_end"],
    )
    hunter.blocked_event.unlock.assert_awaited_once_with(room, "1001", [])


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skill__no_args_or_bad_args_send_usage(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    hunter = CharacterHunter(room, players[0])
    players[0].role = hunter
    hunter.skill_available = True

    await hunter.on_skill(room, "1001", [])
    assert "用法" in fake_io["private_messages"][-1][1]

    await hunter.on_skill(room, "1001", ["shoot", "x"])
    assert "编号需要是数字" in fake_io["private_messages"][-1][1]


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skill__invalid_or_dead_target(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 2, 1001)
    hunter = CharacterHunter(room, players[0])
    players[0].role = hunter
    players[1].role = CharacterPerson(room, players[1])
    hunter.skill_available = True

    await hunter.on_skill(room, "1001", ["shoot", "9"])
    assert "目标编号无效" in fake_io["private_messages"][-1][1]

    players[1].alive = False
    await hunter.on_skill(room, "1001", ["shoot", "2"])
    assert "目标已死亡" in fake_io["private_messages"][-1][1]


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skill__wrong_user_or_unavailable_or_invalid_op_ignored(
    room_factory, players_factory
) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    hunter = CharacterHunter(room, players[0])
    players[0].role = hunter

    hunter.skill_available = True
    await hunter.on_skill(room, "2001", ["shoot", "1"])
    assert hunter.skill_available is True

    hunter.skill_available = False
    await hunter.on_skill(room, "1001", ["shoot", "1"])
    assert hunter.skill_available is False

    hunter.skill_available = True
    await hunter.on_skill(room, "1001", ["other", "1"])
    assert hunter.skill_available is True


@pytest.mark.asyncio
async def test_on_skip__spec_empty_args_should_skip(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    hunter = CharacterHunter(room, players[0])
    players[0].role = hunter
    hunter.skill_available = True
    hunter.blocked_event = AsyncMock()

    await hunter.on_skip(room, "1001", [])

    assert hunter.skill_available is False
    hunter.blocked_event.unlock.assert_awaited_once_with(room, "1001", [])


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skip__with_args_disables_skill_and_unlocks(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    hunter = CharacterHunter(room, players[0])
    players[0].role = hunter
    hunter.skill_available = True
    hunter.blocked_event = AsyncMock()

    await hunter.on_skip(room, "1001", ["confirm"])

    assert "放弃使用技能" in fake_io["private_messages"][-1][1]
    assert hunter.skill_available is False
    hunter.blocked_event.unlock.assert_awaited_once_with(room, "1001", [])


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skip__not_available_or_wrong_user_ignored(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    hunter = CharacterHunter(room, players[0])
    players[0].role = hunter

    hunter.skill_available = False
    await hunter.on_skip(room, "1001", ["x"])
    assert hunter.skill_available is False

    hunter.skill_available = True
    await hunter.on_skip(room, "2001", ["x"])
    assert hunter.skill_available is True
