from __future__ import annotations

import pytest

from game.event_base import EventBase
from game.event_system import EventSystem


@pytest.mark.unit
def test_init__contains_builtin_events() -> None:
    es = EventSystem()
    expected_names = {
        "game_start",
        "night_start",
        "day_start",
        "vote_start",
        "night_end",
        "vote_end",
        "day_end",
        "game_end",
        "skill",
        "vote",
        "skip",
        "person_killed",
    }

    assert expected_names.issubset(set(es.events.keys()))
    assert es.event_game_start is es.events["game_start"]
    assert es.event_person_killed is es.events["person_killed"]


@pytest.mark.unit
def test_new_event__registers_to_events_dict() -> None:
    es = EventSystem()

    evt = es._new_event("custom_evt")

    assert isinstance(evt, EventBase)
    assert es.events["custom_evt"] is evt


@pytest.mark.unit
def test_get_event__missing_returns_none() -> None:
    es = EventSystem()
    assert es.get_event("not_exist") is None


@pytest.mark.unit
def test_get_or_create_event__idempotent_for_same_name() -> None:
    es = EventSystem()

    first = es.get_or_create_event("seer_check")
    second = es.get_or_create_event("seer_check")

    assert first is second
    assert es.get_event("seer_check") is first
