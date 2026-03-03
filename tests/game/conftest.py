from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import sys
from unittest.mock import AsyncMock

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from game.event_base import EventBase
from game.player import Player
from game.room import Room


@pytest.fixture
def fake_io() -> dict[str, object]:
    group_messages: list[tuple[int, str]] = []
    private_messages: list[tuple[int, str]] = []

    async def send_group_msg(*, group_id: int, message: str) -> None:
        group_messages.append((group_id, message))

    async def send_private_msg(*, user_id: int, message: str) -> None:
        private_messages.append((user_id, message))

    return {
        "send_group_msg": send_group_msg,
        "send_private_msg": send_private_msg,
        "group_messages": group_messages,
        "private_messages": private_messages,
    }


@pytest.fixture
def room_factory(fake_io: dict[str, object]) -> Callable[[str], Room]:
    def _factory(group_id: str = "10000") -> Room:
        return Room(
            group_id,
            fake_io["send_group_msg"],
            fake_io["send_private_msg"],
        )

    return _factory


@pytest.fixture
def players_factory() -> Callable[[Room, int, int], list[Player]]:
    def _factory(room: Room, count: int = 4, start_user_id: int = 1000) -> list[Player]:
        room.player_list = []
        room.id_2_player = {}
        players: list[Player] = []
        for idx in range(count):
            uid = str(start_user_id + idx)
            p = Player(uid, idx)
            room.player_list.append(p)
            room.id_2_player[uid] = p
            players.append(p)
        return players

    return _factory


@pytest.fixture
def event_spy() -> Callable[[EventBase, int], list[tuple[object, str | None, list[str]]]]:
    calls: list[tuple[object, str | None, list[str]]] = []

    async def _listener(room: object, user_id: str | None, args: list[str]) -> None:
        calls.append((room, user_id, list(args)))

    def _attach(event: EventBase, priority: int = 0) -> list[tuple[object, str | None, list[str]]]:
        event.add_listener(_listener, priority=priority)
        return calls

    return _attach


@pytest.fixture
def async_mock() -> Callable[[], AsyncMock]:
    return AsyncMock
