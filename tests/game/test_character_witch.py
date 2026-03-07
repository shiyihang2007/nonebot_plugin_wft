from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from game.character_person import CharacterPerson
from game.character_witch import CharacterWitch


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_night_start__reset_flags(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    witch = CharacterWitch(room, players[0])

    witch._skill_available = True
    witch._wolf_kill_target_user_id = "1002"

    await witch.on_night_start(room, None, [])

    assert witch._skill_available is False
    assert witch._wolf_kill_target_user_id is None


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_wolf_locked__preconditions_block(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    witch = CharacterWitch(room, players[0])
    players[0].role = witch

    players[0].alive = False
    await witch.on_wolf_locked(room, None, ["1001"])
    assert witch._skill_available is False
    players[0].alive = True

    room.state = "speech"
    await witch.on_wolf_locked(room, None, ["1001"])
    assert witch._skill_available is False

    room.state = "night"
    witch.has_antidote = False
    witch.has_poison = False
    await witch.on_wolf_locked(room, None, ["1001"])
    assert witch._skill_available is False


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_wolf_locked__enable_skill_and_prompt(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 2, 1001)
    witch = CharacterWitch(room, players[0])
    players[0].role = witch
    players[1].role = CharacterPerson(room, players[1])
    room.state = "night"

    await witch.on_wolf_locked(room, None, ["1002"])

    assert witch._skill_available is True
    assert witch._wolf_kill_target_user_id == "1002"
    assert room.events_system.event_night_end.lock_count >= 1
    assert "你是女巫" in fake_io["private_messages"][-1][1]
    assert "当前狼刀落在" in fake_io["private_messages"][-1][1]


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_wolf_locked__no_target_tip_when_empty(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    witch = CharacterWitch(room, players[0])
    players[0].role = witch
    room.state = "night"

    await witch.on_wolf_locked(room, None, [""])

    assert "当前狼刀未指定" in fake_io["private_messages"][-1][1]


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skill__precondition_guards(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    witch = CharacterWitch(room, players[0])
    players[0].role = witch

    room.state = "night"
    await witch.on_skill(room, "2001", ["save"])
    assert fake_io["private_messages"] == []

    players[0].alive = False
    await witch.on_skill(room, "1001", ["save"])
    assert fake_io["private_messages"] == []
    players[0].alive = True

    room.state = "speech"
    await witch.on_skill(room, "1001", ["save"])
    assert fake_io["private_messages"] == []

    room.state = "night"
    witch._skill_available = False
    await witch.on_skill(room, "1001", ["save"])
    assert fake_io["private_messages"] == []

    witch._skill_available = True
    await witch.on_skill(room, "1001", [])
    assert fake_io["private_messages"] == []


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skill__save_successfully_removes_pending_death(
    room_factory, players_factory, fake_io
) -> None:
    room = room_factory()
    players = players_factory(room, 2, 1001)
    witch = CharacterWitch(room, players[0])
    players[0].role = witch
    players[1].role = CharacterPerson(room, players[1])
    room.state = "night"

    witch._skill_available = True
    witch._wolf_kill_target_user_id = "1002"
    room.pending_death_records["1002"] = "被狼刀了"

    await witch.on_skill(room, "1001", ["save"])

    assert "1002" not in room.pending_death_records
    assert witch.has_antidote is False
    assert "救下了" in fake_io["private_messages"][-1][1]


@pytest.mark.asyncio
async def test_on_skill__spec_save_without_target_should_not_consume_antidote(
    room_factory, players_factory
) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    witch = CharacterWitch(room, players[0])
    players[0].role = witch
    room.state = "night"
    witch._skill_available = True
    witch._wolf_kill_target_user_id = "9999"

    await witch.on_skill(room, "1001", ["save"])

    assert witch.has_antidote is True


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skill__save_when_antidote_empty(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    witch = CharacterWitch(room, players[0])
    players[0].role = witch
    room.state = "night"
    witch._skill_available = True
    witch.has_antidote = False

    await witch.on_skill(room, "1001", ["save"])

    assert "解药已用完" in fake_io["private_messages"][-1][1]


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skill__poison_branch_invalid_cases(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 2, 1001)
    witch = CharacterWitch(room, players[0])
    players[0].role = witch
    players[1].role = CharacterPerson(room, players[1])
    room.state = "night"
    witch._skill_available = True

    witch.has_poison = False
    await witch.on_skill(room, "1001", ["poison", "2"])
    assert "毒药已用完" in fake_io["private_messages"][-1][1]

    witch.has_poison = True
    await witch.on_skill(room, "1001", ["poison", "x"])
    assert "编号需要是数字" in fake_io["private_messages"][-1][1]

    await witch.on_skill(room, "1001", ["poison", "9"])
    assert "目标编号无效" in fake_io["private_messages"][-1][1]

    players[1].alive = False
    await witch.on_skill(room, "1001", ["poison", "2"])
    assert "目标已死亡" in fake_io["private_messages"][-1][1]

    players[1].alive = True
    await witch.on_skill(room, "1001", ["poison", "1"])
    assert "不能对自己使用毒药" in fake_io["private_messages"][-1][1]


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skill__poison_valid_target(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 2, 1001)
    witch = CharacterWitch(room, players[0])
    players[0].role = witch
    players[1].role = CharacterPerson(room, players[1])
    room.state = "night"
    witch._skill_available = True
    witch.has_antidote = False
    room.events_system.event_night_end.unlock = AsyncMock()

    await witch.on_skill(room, "1001", ["poison", "2"])

    assert room.pending_death_records["1002"] == "被毒死了"
    assert witch.has_poison is False
    assert witch._skill_available is False
    room.events_system.event_night_end.unlock.assert_awaited_once_with(room, "1001", [])
    assert "药水已用完" in fake_io["private_messages"][-1][1]


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skip__disable_skill_and_unlock(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    witch = CharacterWitch(room, players[0])
    players[0].role = witch
    room.state = "night"
    witch._skill_available = True
    room.events_system.event_night_end.unlock = AsyncMock()

    await witch.on_skip(room, "1001", [])

    assert witch._skill_available is False
    assert "放弃本夜用药" in fake_io["private_messages"][-1][1]
    room.events_system.event_night_end.unlock.assert_awaited_once_with(room, "1001", [])


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_skip__wrong_user_or_stage_or_unavailable_ignored(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    witch = CharacterWitch(room, players[0])
    players[0].role = witch

    room.state = "night"
    witch._skill_available = True
    await witch.on_skip(room, "2001", [])
    assert witch._skill_available is True

    room.state = "speech"
    await witch.on_skip(room, "1001", [])
    assert witch._skill_available is True

    room.state = "night"
    witch._skill_available = False
    await witch.on_skip(room, "1001", [])
    assert witch._skill_available is False
