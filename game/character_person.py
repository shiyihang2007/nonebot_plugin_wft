"""Villager role (no active skills)."""

from __future__ import annotations

from .character_base import CharacterBase


class CharacterPerson(CharacterBase):
    """村民：无主动技能。"""

    role_id = "person"
    name = "村民"
    camp = "good"
    aliases = ["person", "人", "民", "村民"]
