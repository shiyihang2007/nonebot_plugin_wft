from __future__ import annotations

from unittest.mock import patch

import pytest

from game.character_person import CharacterPerson
from game.character_wolf import CharacterWolf
from game.room import get_character_class_by_alias


@pytest.mark.unit
def test_room_init__sets_expected_defaults(room_factory) -> None:
    room = room_factory("24680")

    assert room.group_id == "24680"
    assert room.state == "lobby"
    assert room.player_list == []
    assert room.id_2_player == {}
    assert room.character_enabled == {}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_broadcast_and_post_to_player__call_injected_io(room_factory, fake_io) -> None:
    room = room_factory("200")

    await room.broadcast("群消息")
    await room.post_to_player("300", "私聊")

    assert fake_io["group_messages"] == [(200, "群消息")]
    assert fake_io["private_messages"] == [(300, "私聊")]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_add_player__normal_join(room_factory, fake_io) -> None:
    room = room_factory()

    await room.add_player("1001")

    assert "1001" in room.id_2_player
    assert room.player_list[0].user_id == "1001"
    assert "已加入游戏" in fake_io["group_messages"][-1][1]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_add_player__duplicate_in_non_debug_mode(room_factory, fake_io) -> None:
    room = room_factory()
    await room.add_player("1001")

    await room.add_player("1001")

    assert len(room.player_list) == 1
    assert "已在房间内" in fake_io["group_messages"][-1][1]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_add_player__duplicate_in_debug_mode_creates_shadow_uid(room_factory) -> None:
    room = room_factory()
    room.settings.debug = True
    await room.add_player("1001")

    with patch("game.room.random.randint", return_value=0x1234):
        await room.add_player("1001")

    assert len(room.player_list) == 2
    assert any(k.startswith("1001_") for k in room.id_2_player)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_remove_player__missing_player(room_factory, fake_io) -> None:
    room = room_factory()

    await room.remove_player("999")

    assert "不存在于房间内" in fake_io["group_messages"][-1][1]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_remove_player__reorder_after_remove(room_factory) -> None:
    room = room_factory()
    await room.add_player("1001")
    await room.add_player("1002")
    await room.add_player("1003")

    await room.remove_player("1002")

    assert [p.user_id for p in room.player_list] == ["1001", "1003"]
    assert [p.order for p in room.player_list] == [0, 1]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_add_character__mixed_aliases(room_factory, fake_io) -> None:
    room = room_factory()

    await room.add_character(["狼", "不存在", "", "  "])

    wolf_cls = get_character_class_by_alias("狼")
    assert wolf_cls is not None
    assert room.character_enabled[wolf_cls] == 1
    message = fake_io["group_messages"][-1][1]
    assert "添加了角色" in message
    assert "未知角色别名" in message


@pytest.mark.unit
@pytest.mark.asyncio
async def test_add_character__empty_input_reports_no_add(room_factory, fake_io) -> None:
    room = room_factory()

    await room.add_character(["", "   "])

    assert fake_io["group_messages"][-1][1] == "没有添加任何角色"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_remove_character__removed_not_enabled_and_unknown(room_factory, fake_io) -> None:
    room = room_factory()
    await room.add_character(["狼", "狼"])

    await room.remove_character(["狼", "狼", "狼", "未知角色"]) 

    wolf_cls = get_character_class_by_alias("狼")
    assert wolf_cls is not None
    assert wolf_cls not in room.character_enabled
    message = fake_io["group_messages"][-1][1]
    assert "角色不存在" in message
    assert "未知角色" in message


@pytest.mark.unit
@pytest.mark.asyncio
async def test_remove_character__empty_input_reports_no_remove(room_factory, fake_io) -> None:
    room = room_factory()

    await room.remove_character(["", "   "])

    assert fake_io["group_messages"][-1][1] == "没有移除任何角色"


@pytest.mark.unit
def test_get_player_by_seat__invalid_and_valid(room_factory, players_factory) -> None:
    room = room_factory()
    players_factory(room, 3, 1001)

    assert room.get_player_by_seat(0) is None
    assert room.get_player_by_seat(4) is None
    assert room.get_player_by_seat(2) is room.player_list[1]


@pytest.mark.unit
def test_alive_related_queries__return_expected_sets(room_factory, players_factory) -> None:
    room = room_factory()
    players = players_factory(room, 3, 1001)
    players[0].role = CharacterPerson(room, players[0])
    players[1].role = CharacterWolf(room, players[1])
    players[2].role = CharacterPerson(room, players[2])
    players[2].alive = False

    alive = room.alive_players()
    assert [p.user_id for p in alive] == ["1001", "1002"]
    assert room.alive_user_ids() == {"1001", "1002"}
    assert room.alive_role_user_ids("wolf") == {"1002"}


@pytest.mark.unit
def test_players_overview_lines__include_seat_and_alive_status(
    room_factory, players_factory
) -> None:
    room = room_factory()
    players = players_factory(room, 2, 1001)
    players[1].alive = False

    lines = room.players_overview_lines()

    assert lines == [
        "1号 [CQ:at,qq=1001] - 存活",
        "2号 [CQ:at,qq=1002] - 死亡",
    ]


@pytest.mark.unit
def test_players_overview_lines__empty_room_returns_empty_list(room_factory) -> None:
    room = room_factory()

    assert room.players_overview_lines() == []
