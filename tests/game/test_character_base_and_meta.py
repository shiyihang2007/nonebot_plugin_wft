from __future__ import annotations

import pytest

from game.character_base import CharacterBase
from game.character_god import CharacterGod
from game.character_person import CharacterPerson


class DummyRole(CharacterBase):
    role_id = "dummy"
    name = "测试角色"
    camp = "good"
    aliases = ["dummy"]


@pytest.mark.character
def test_character_base_init__registers_death_listener(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)

    role = DummyRole(room, players[0])

    listeners = [listener for _, listener in room.events_system.event_person_killed._listeners]
    assert any(getattr(x, "__self__", None) is role for x in listeners)


@pytest.mark.character
def test_character_base_properties__mirror_player(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    role = DummyRole(room, players[0])

    assert role.user_id == "1001"
    assert role.alive is True

    players[0].alive = False
    assert role.alive is False


@pytest.mark.character
@pytest.mark.asyncio
async def test_send_private__delegates_to_room(room_factory, fake_io, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    role = DummyRole(room, players[0])

    await role.send_private("hello")

    assert fake_io["private_messages"][-1] == (1001, "hello")


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_person_killed_update__ignore_other_user(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    role = DummyRole(room, players[0])

    await role.on_person_killed_update(room, "2002", ["原因", "day_end"])

    assert players[0].alive is True
    assert fake_io["private_messages"] == []


@pytest.mark.character
@pytest.mark.asyncio
async def test_on_person_killed_update__set_dead_and_notify(room_factory, players_factory, fake_io) -> None:
    room = room_factory()
    players = players_factory(room, 1, 1001)
    role = DummyRole(room, players[0])

    await role.on_person_killed_update(room, "1001", ["被票出", "day_end"])

    assert players[0].alive is False
    assert "你已死亡" in fake_io["private_messages"][-1][1]


@pytest.mark.character
def test_character_meta__god_and_person_constants() -> None:
    assert CharacterGod.role_id == "god"
    assert CharacterGod.camp == "good"

    assert CharacterPerson.role_id == "person"
    assert CharacterPerson.camp == "good"
    assert "村民" in CharacterPerson.aliases
