from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from game.character_person import CharacterPerson
from game.character_wolf import CharacterWolf


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_night_start__alive_resets_and_locks(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 2, 1001)
    wolf = CharacterWolf(room, players[0])
    players[0].role = wolf

    await wolf.on_night_start(room, None, [])

    assert wolf.kill_responded is False
    assert wolf.night_vote_target_user_id is None
    assert wolf.skill_kill_available is True
    assert room.events_system.event_night_end.lock_count >= 1
    assert "你是狼人" in fake_io["private_messages"][-1][1]


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_night_start__dead_user_ignored(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    wolf = CharacterWolf(room, players[0])
    players[0].role = wolf
    players[0].alive = False
    lock_before = room.events_system.event_night_end.lock_count

    await wolf.on_night_start(room, None, [])

    assert room.events_system.event_night_end.lock_count == lock_before


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skill__wrong_stage_rejected(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 2, 1001)
    wolf = CharacterWolf(room, players[0])
    players[0].role = wolf
    room.state = "speech"
    wolf.skill_kill_available = True

    await wolf.on_skill(room, "1001", ["kill", "2"])

    assert "现在不是夜晚阶段" in fake_io["private_messages"][-1][1]


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skill__precondition_guards(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    wolf = CharacterWolf(room, players[0])
    players[0].role = wolf
    room.state = "night"

    await wolf.on_skill(room, "2001", ["kill", "1"])
    assert wolf.night_vote_target_user_id is None

    wolf.skill_kill_available = False
    await wolf.on_skill(room, "1001", ["kill", "1"])
    assert wolf.night_vote_target_user_id is None

    wolf.skill_kill_available = True
    await wolf.on_skill(room, "1001", [])
    assert wolf.night_vote_target_user_id is None

    await wolf.on_skill(room, "1001", ["bad", "1"])
    assert wolf.night_vote_target_user_id is None


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skill__invalid_args_and_targets(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 2, 1001)
    wolf = CharacterWolf(room, players[0])
    players[0].role = wolf
    players[1].role = CharacterPerson(room, players[1])
    room.state = "night"
    wolf.skill_kill_available = True

    await wolf.on_skill(room, "1001", ["kill", "x"])
    assert "编号需要是数字" in fake_io["private_messages"][-1][1]

    await wolf.on_skill(room, "1001", ["kill", "9"])
    assert "目标编号无效" in fake_io["private_messages"][-1][1]

    players[1].alive = False
    await wolf.on_skill(room, "1001", ["kill", "2"])
    assert "目标已死亡" in fake_io["private_messages"][-1][1]

    players[1].alive = True
    await wolf.on_skill(room, "1001", ["kill", "1"])
    assert "不能选择自己" in fake_io["private_messages"][-1][1]


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skill__valid_vote_sets_target_and_try_lock(room_factory, players_factory, monkeypatch, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 2, 1001)
    wolf = CharacterWolf(room, players[0])
    players[0].role = wolf
    players[1].role = CharacterPerson(room, players[1])
    room.state = "night"
    wolf.skill_kill_available = True
    wolf._try_lock_pack = AsyncMock()

    await wolf.on_skill(room, "1001", ["kill", "2"])

    assert wolf.night_vote_target_user_id == "1002"
    assert wolf.kill_responded is True
    assert "已投票击杀" in fake_io["private_messages"][-1][1]
    wolf._try_lock_pack.assert_awaited_once()


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skip__precondition_guards(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    wolf = CharacterWolf(room, players[0])
    players[0].role = wolf
    wolf._try_lock_pack = AsyncMock()

    await wolf.on_skip(room, "2001", [])
    wolf._try_lock_pack.assert_not_awaited()

    wolf.skill_kill_available = False
    await wolf.on_skip(room, "1001", [])
    wolf._try_lock_pack.assert_not_awaited()


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skip__mark_responded_and_try_lock(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    wolf = CharacterWolf(room, players[0])
    players[0].role = wolf
    wolf.skill_kill_available = True
    wolf._try_lock_pack = AsyncMock()

    await wolf.on_skip(room, "1001", [])

    assert wolf.kill_responded is True
    assert wolf.night_vote_target_user_id is None
    assert "放弃本夜击杀" in fake_io["private_messages"][-1][1]
    wolf._try_lock_pack.assert_awaited_once()


@pytest.mark.character
def test_alive_wolves__returns_only_alive_wolf_instances(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 3, 1001)
    wolf1 = CharacterWolf(room, players[0])
    wolf2 = CharacterWolf(room, players[1])
    villager = CharacterPerson(room, players[2])
    players[0].role = wolf1
    players[1].role = wolf2
    players[2].role = villager
    players[1].alive = False

    alive_wolves = wolf1._alive_wolves()

    assert alive_wolves == [wolf1]


@pytest.mark.character
@pytest.mark.asyncio
async def test_try_lock_pack__majority_vote_locks_target(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 3, 1001)
    wolf1 = CharacterWolf(room, players[0])
    wolf2 = CharacterWolf(room, players[1])
    target = CharacterPerson(room, players[2])
    players[0].role = wolf1
    players[1].role = wolf2
    players[2].role = target
    wolf1.night_vote_target_user_id = "1003"
    wolf2.night_vote_target_user_id = "1003"
    wolf1.kill_responded = True
    wolf2.kill_responded = True
    wolf1.event_wolf_locked.active = AsyncMock()

    await wolf1._try_lock_pack()

    wolf1.event_wolf_locked.active.assert_awaited_once_with(room, wolf1.name, ["1003"])
    assert room.pending_death_records["1003"] == "被狼刀了"


@pytest.mark.character
@pytest.mark.asyncio
async def test_try_lock_pack__all_responded_without_majority_sends_empty_target(
    room_factory, players_factory
) -> None:
    room = room_factory()
    players = players_factory(room, 3, 1001)
    wolf1 = CharacterWolf(room, players[0])
    wolf2 = CharacterWolf(room, players[1])
    players[0].role = wolf1
    players[1].role = wolf2
    players[2].role = CharacterPerson(room, players[2])
    wolf1.night_vote_target_user_id = "1003"
    wolf2.night_vote_target_user_id = "1002"
    wolf1.kill_responded = True
    wolf2.kill_responded = True
    wolf1.event_wolf_locked.active = AsyncMock()

    await wolf1._try_lock_pack()

    wolf1.event_wolf_locked.active.assert_awaited_once_with(room, wolf1.name, [""])


@pytest.mark.character
@pytest.mark.asyncio
async def test_try_lock_pack__no_votes_and_not_all_responded_do_nothing(
    room_factory, players_factory
) -> None:
    room = room_factory()
    players = players_factory(room, 2, 1001)
    wolf1 = CharacterWolf(room, players[0])
    wolf2 = CharacterWolf(room, players[1])
    players[0].role = wolf1
    players[1].role = wolf2
    wolf1.kill_responded = True
    wolf2.kill_responded = False
    wolf1.event_wolf_locked.active = AsyncMock()

    await wolf1._try_lock_pack()

    wolf1.event_wolf_locked.active.assert_not_awaited()


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_wolf_locked__disable_skill(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    wolf = CharacterWolf(room, players[0])
    wolf.skill_kill_available = True

    await wolf.on_wolf_locked(room, None, [])

    assert wolf.skill_kill_available is False
