"""Base class for god roles (good camp with night skills)."""

from __future__ import annotations

from .character_base import CharacterBase

class CharacterGod(CharacterBase):
    """神职角色基类。"""

    role_id = "god"
    camp = "good"
