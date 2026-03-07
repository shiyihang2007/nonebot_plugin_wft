from __future__ import annotations

import types

import pytest

from game.character_base import CharacterBase
from game.room import (
    _build_character_registry,
    _load_character_classes,
    get_character_class_by_alias,
    get_character_class_by_role_id,
)


@pytest.mark.unit
def test_build_character_registry__filters_invalid_and_conflicts(caplog) -> None:
    class RoleA(CharacterBase):
        role_id = "a"
        aliases = ["A", "x"]
        camp = "good"
        name = "A"

    class RoleA2(CharacterBase):
        role_id = "a"
        aliases = ["A2"]
        camp = "good"
        name = "A2"

    class RoleB(CharacterBase):
        role_id = "b"
        aliases = ["x", "B"]
        camp = "wolf"
        name = "B"

    class RoleBad(CharacterBase):
        role_id = ""
        aliases = ["bad"]

    with caplog.at_level("WARNING"):
        classes, role_map, alias_map = _build_character_registry(
            [RoleA, RoleA2, RoleB, RoleBad]
        )

    assert RoleA in classes
    assert RoleB in classes
    assert RoleBad not in classes
    assert role_map["a"] is RoleA
    assert role_map["b"] is RoleB
    assert alias_map["A"] is RoleA
    assert alias_map["B"] is RoleB
    assert alias_map["x"] is RoleA


@pytest.mark.unit
def test_build_character_registry__ignore_non_list_alias_and_invalid_alias_item() -> None:
    class RoleC(CharacterBase):
        role_id = "c"
        aliases = "not-list"
        camp = "good"
        name = "C"

    class RoleD(CharacterBase):
        role_id = "d"
        aliases = ["", 123, "D"]
        camp = "good"
        name = "D"

    classes, role_map, alias_map = _build_character_registry([RoleC, RoleD])

    assert RoleC in classes and RoleD in classes
    assert role_map["c"] is RoleC
    assert role_map["d"] is RoleD
    assert "D" in alias_map
    assert "" not in alias_map


@pytest.mark.unit
def test_get_character_class_lookup__works_for_builtin_roles() -> None:
    wolf_cls = get_character_class_by_role_id("wolf")
    wolf_alias_cls = get_character_class_by_alias("狼")

    assert wolf_cls is not None
    assert wolf_alias_cls is not None
    assert wolf_cls is wolf_alias_cls


@pytest.mark.unit
def test_load_character_classes__keeps_only_local_character_subclasses(monkeypatch) -> None:
    dummy_module = types.ModuleType("game.character_dummy")

    LocalRole = type(
        "LocalRole",
        (CharacterBase,),
        {
            "__module__": "game.character_dummy",
            "role_id": "local",
            "name": "local",
            "camp": "good",
            "aliases": [],
        },
    )
    ForeignRole = type(
        "ForeignRole",
        (CharacterBase,),
        {
            "__module__": "other.module",
            "role_id": "foreign",
            "name": "foreign",
            "camp": "good",
            "aliases": [],
        },
    )
    NotClass = 123

    from game import room as room_mod

    monkeypatch.setattr(
        room_mod,
        "get_modules_in_package_by_prefix",
        lambda package, prefix: [dummy_module],
    )
    monkeypatch.setattr(
        room_mod,
        "get_classes_in_module",
        lambda module: [LocalRole, ForeignRole, NotClass],
    )

    classes = _load_character_classes()
    assert classes == [LocalRole]


@pytest.mark.unit
def test_load_character_classes__non_class_with_matching_module_hits_typeerror_branch(
    monkeypatch,
) -> None:
    dummy_module = types.ModuleType("game.character_dummy_2")

    LocalRole = type(
        "LocalRole2",
        (CharacterBase,),
        {
            "__module__": "game.character_dummy_2",
            "role_id": "local2",
            "name": "local2",
            "camp": "good",
            "aliases": [],
        },
    )

    class NonClass:
        pass

    obj = NonClass()
    obj.__module__ = "game.character_dummy_2"

    from game import room as room_mod

    monkeypatch.setattr(
        room_mod,
        "get_modules_in_package_by_prefix",
        lambda package, prefix: [dummy_module],
    )
    monkeypatch.setattr(
        room_mod,
        "get_classes_in_module",
        lambda module: [LocalRole, obj],
    )

    classes = _load_character_classes()
    assert classes == [LocalRole]
