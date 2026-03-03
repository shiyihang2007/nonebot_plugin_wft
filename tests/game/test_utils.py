from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

from game import utils


def _clear_modules(prefix: str) -> None:
    for name in list(sys.modules):
        if name == prefix or name.startswith(f"{prefix}."):
            sys.modules.pop(name, None)


def test_get_classes_in_module__returns_only_classes() -> None:
    module = types.ModuleType("tmp_module")

    class A: ...

    class B: ...

    module.A = A
    module.B = B
    module.VALUE = 1

    classes = utils.get_classes_in_module(module)
    assert A in classes
    assert B in classes
    assert all(isinstance(x, type) for x in classes)


def test_get_module_in_directory__package_missing_returns_empty() -> None:
    modules = utils.get_module_in_directory("pkg_not_exist_abc", "mods")
    assert modules == []


def test_get_module_in_directory__imports_all_modules(tmp_path: Path, monkeypatch) -> None:
    package = "tmp_pkg_utils_1"
    _clear_modules(package)
    root = tmp_path / package
    mods = root / "mods"
    mods.mkdir(parents=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    (mods / "__init__.py").write_text("", encoding="utf-8")
    (mods / "a.py").write_text("VALUE = 'A'\n", encoding="utf-8")
    (mods / "b.py").write_text("VALUE = 'B'\n", encoding="utf-8")

    monkeypatch.syspath_prepend(str(tmp_path))
    modules = utils.get_module_in_directory(package, "mods")

    names = sorted(x.__name__ for x in modules)
    assert names == [f"{package}.mods.a", f"{package}.mods.b"]


def test_get_modules_in_package_by_prefix__package_none_returns_empty() -> None:
    assert utils.get_modules_in_package_by_prefix(None, "character_") == []


def test_get_modules_in_package_by_prefix__package_missing_returns_empty() -> None:
    assert utils.get_modules_in_package_by_prefix("pkg_not_exist_xyz", "character_") == []


def test_get_modules_in_package_by_prefix__module_without_path_returns_empty(
    tmp_path: Path, monkeypatch
) -> None:
    module_name = "tmp_utils_single_module"
    _clear_modules(module_name)
    (tmp_path / f"{module_name}.py").write_text("X = 1\n", encoding="utf-8")

    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.import_module(module_name)

    assert utils.get_modules_in_package_by_prefix(module_name, "character_") == []


def test_get_modules_in_package_by_prefix__filters_by_prefix(
    tmp_path: Path, monkeypatch
) -> None:
    package = "tmp_pkg_utils_2"
    _clear_modules(package)
    root = tmp_path / package
    root.mkdir(parents=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "character_a.py").write_text("V='a'\n", encoding="utf-8")
    (root / "character_b.py").write_text("V='b'\n", encoding="utf-8")
    (root / "other_c.py").write_text("V='c'\n", encoding="utf-8")

    monkeypatch.syspath_prepend(str(tmp_path))
    modules = utils.get_modules_in_package_by_prefix(package, "character_")

    names = sorted(x.__name__ for x in modules)
    assert names == [f"{package}.character_a", f"{package}.character_b"]
