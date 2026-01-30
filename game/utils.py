"""Lightweight reflection helpers used by the plugin (dynamic role loading)."""

from __future__ import annotations

import importlib
import pkgutil


def get_classes_in_module(module: object) -> list[type]:
    """Return all classes defined in a module object."""
    classes = []
    for name in dir(module):
        member = getattr(module, name)
        if isinstance(member, type):
            classes.append(member)
    return classes


def get_module_in_directory(package: str, directory: str) -> list[object]:
    """Import all modules under a subpackage directory (package.directory.*)."""
    modules = []
    full_package_name = f"{package}.{directory}"
    try:
        pkg = importlib.import_module(full_package_name)
    except ModuleNotFoundError:
        return modules
    for _, module_name, _ in pkgutil.iter_modules(pkg.__path__):
        modules.append(importlib.import_module(f"{full_package_name}.{module_name}"))
    return modules


def get_modules_in_package_by_prefix(package: str | None, prefix: str) -> list[object]:
    """Import all modules under a package whose module name starts with prefix."""
    if not package:
        return []
    modules = []
    try:
        pkg = importlib.import_module(package)
    except ModuleNotFoundError:
        return modules
    if not hasattr(pkg, "__path__"):
        return modules
    for _, module_name, _ in pkgutil.iter_modules(pkg.__path__):
        if module_name.startswith(prefix):
            modules.append(importlib.import_module(f"{package}.{module_name}"))
    return modules
