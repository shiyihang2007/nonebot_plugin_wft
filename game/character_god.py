"""神职角色基类（好人阵营，通常拥有夜晚技能）。"""

from __future__ import annotations

from .character_base import CharacterBase

class CharacterGod(CharacterBase):
    """神职角色基类。"""

    role_id = "god"
    camp = "good"
