from event_base import EventBase


class EventSystem:
    def __init__(self):
        self.event_night_start = EventBase()
        self.event_person_killed = EventBase()
        self.event_day_start = EventBase()
        self.event_vote_start = EventBase()

        self.event_use_skill = EventBase()
