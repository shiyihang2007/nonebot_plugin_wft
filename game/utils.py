"""插件使用的轻量反射工具（用于动态加载角色）。"""

from __future__ import annotations

import importlib
import pkgutil


def get_classes_in_module(module: object) -> list[type]:
    """返回模块对象中定义的所有类。"""
    classes = []
    for name in dir(module):
        member = getattr(module, name)
        if isinstance(member, type):
            classes.append(member)
    return classes


def get_module_in_directory(package: str, directory: str) -> list[object]:
    """导入子包目录下的所有模块（`package.directory.*`）。"""
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
    """导入包下所有以 `prefix` 开头的模块。"""
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
