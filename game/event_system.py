"""Event container for a single Room instance."""

from __future__ import annotations

from .event_base import EventBase


class EventSystem:
    """A set of event channels used by role listeners."""

    def __init__(self) -> None:
        self.event_night_start = EventBase()
        self.event_day_start = EventBase()
        self.event_vote_start = EventBase()

        self.event_use_skill = EventBase()
        self.event_person_killed = EventBase()
