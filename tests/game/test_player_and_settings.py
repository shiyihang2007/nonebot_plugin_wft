from __future__ import annotations

import pytest

from game.player import Player
from game.room_settings import RoomSettings


@pytest.mark.unit
def test_player_init_and_seat__set_expected_defaults() -> None:
    player = Player("12345", 2)

    assert player.user_id == "12345"
    assert player.order == 2
    assert player.alive is True
    assert player.role is None
    assert player.seat == 3


@pytest.mark.unit
def test_room_settings__default_and_override() -> None:
    default_settings = RoomSettings()
    debug_settings = RoomSettings(debug=True)

    assert default_settings.debug is False
    assert debug_settings.debug is True
