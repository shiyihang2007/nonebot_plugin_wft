from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from game.character_black_wolf import CharacterBlackWolf
from game.character_person import CharacterPerson


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_killed__poisoned_cannot_shoot(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    black_wolf = CharacterBlackWolf(room, players[0])
    players[0].role = black_wolf

    await black_wolf.on_killed(room, "1001", ["被毒死了", "day_end"])

    assert black_wolf.skill_shoot_available is False
    assert "无法使用猎枪" in fake_io["private_messages"][-1][1]


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_killed__other_user_ignored(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    black_wolf = CharacterBlackWolf(room, players[0])
    players[0].role = black_wolf

    await black_wolf.on_killed(room, "2001", ["白天放逐", "day_end"])

    assert black_wolf.skill_shoot_available is False


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_killed__normal_death_locks_event(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    black_wolf = CharacterBlackWolf(room, players[0])
    players[0].role = black_wolf
    initial_lock = room.events_system.event_day_end.lock_count

    await black_wolf.on_killed(room, "1001", ["白天放逐", "day_end"])

    assert black_wolf.skill_shoot_available is True
    assert room.events_system.event_day_end.lock_count == initial_lock + 1
    assert "你是黑狼王" in fake_io["private_messages"][-1][1]


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skill__shoot_valid_target_and_unlock(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 2, 1001)
    black_wolf = CharacterBlackWolf(room, players[0])
    players[0].role = black_wolf
    players[1].role = CharacterPerson(room, players[1])

    black_wolf.skill_shoot_available = True
    black_wolf.blocked_event = AsyncMock()
    black_wolf.blocked_event.name = "day_end"
    room.events_system.event_person_killed.active = AsyncMock()

    await black_wolf.on_skill(room, "1001", ["shoot", "2"])

    assert black_wolf.skill_shoot_available is False
    room.events_system.event_person_killed.active.assert_awaited_once_with(
        black_wolf,
        "1002",
        ["被枪杀", "day_end"],
    )
    black_wolf.blocked_event.unlock.assert_awaited_once_with(room, "1001", [])


@pytest.mark.asyncio
async def test_on_skip__spec_empty_args_should_skip(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    black_wolf = CharacterBlackWolf(room, players[0])
    players[0].role = black_wolf
    black_wolf.skill_shoot_available = True
    black_wolf.blocked_event = AsyncMock()

    await black_wolf.on_skip(room, "1001", [])

    assert black_wolf.skill_shoot_available is False
    black_wolf.blocked_event.unlock.assert_awaited_once_with(room, "1001", [])


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skill__no_args_or_bad_args_send_usage(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    black_wolf = CharacterBlackWolf(room, players[0])
    players[0].role = black_wolf
    black_wolf.skill_shoot_available = True

    await black_wolf.on_skill(room, "1001", [])
    assert "用法" in fake_io["private_messages"][-1][1]

    await black_wolf.on_skill(room, "1001", ["shoot", "x"])
    assert "编号需要是数字" in fake_io["private_messages"][-1][1]


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skill__invalid_or_dead_target(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 2, 1001)
    black_wolf = CharacterBlackWolf(room, players[0])
    players[0].role = black_wolf
    players[1].role = CharacterPerson(room, players[1])
    black_wolf.skill_shoot_available = True

    await black_wolf.on_skill(room, "1001", ["shoot", "9"])
    assert "目标编号无效" in fake_io["private_messages"][-1][1]

    players[1].alive = False
    await black_wolf.on_skill(room, "1001", ["shoot", "2"])
    assert "目标已死亡" in fake_io["private_messages"][-1][1]


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skill__wrong_user_or_unavailable_or_invalid_op_ignored(
    room_factory, players_factory
) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    black_wolf = CharacterBlackWolf(room, players[0])
    players[0].role = black_wolf

    black_wolf.skill_shoot_available = True
    await black_wolf.on_skill(room, "2001", ["shoot", "1"])
    assert black_wolf.skill_shoot_available is True

    black_wolf.skill_shoot_available = False
    await black_wolf.on_skill(room, "1001", ["shoot", "1"])
    assert black_wolf.skill_shoot_available is False

    black_wolf.skill_shoot_available = True
    await black_wolf.on_skill(room, "1001", ["other", "1"])
    assert black_wolf.skill_shoot_available is True


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skip__with_args_disables_skill_and_unlocks(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    black_wolf = CharacterBlackWolf(room, players[0])
    players[0].role = black_wolf
    black_wolf.skill_shoot_available = True
    black_wolf.blocked_event = AsyncMock()

    await black_wolf.on_skip(room, "1001", ["confirm"])

    assert "放弃使用技能" in fake_io["private_messages"][-1][1]
    assert black_wolf.skill_shoot_available is False
    black_wolf.blocked_event.unlock.assert_awaited_once_with(room, "1001", [])


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skip__not_available_or_wrong_user_ignored(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    black_wolf = CharacterBlackWolf(room, players[0])
    players[0].role = black_wolf

    black_wolf.skill_shoot_available = False
    await black_wolf.on_skip(room, "1001", ["x"])
    assert black_wolf.skill_shoot_available is False

    black_wolf.skill_shoot_available = True
    await black_wolf.on_skip(room, "2001", ["x"])
    assert black_wolf.skill_shoot_available is True
