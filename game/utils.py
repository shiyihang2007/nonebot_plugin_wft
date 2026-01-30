import importlib


def get_classes_in_module(module: object) -> list[type]:
    """获取模块中的所有类"""
    classes = []
    for name in dir(module):
        member = getattr(module, name)
        if isinstance(member, type):
            classes.append(member)
    return classes


def get_module_in_directory(package: str, directory: str) -> list[object]:
    """获取目录下的所有模块"""
    import os
    import pkgutil

    modules = []
    package_path = package.replace(".", "/")
    full_path = os.path.join(os.path.dirname(__file__), package_path, directory)
    for _, module_name, _ in pkgutil.iter_modules([full_path]):
        full_module_name = f"{package}.{directory}.{module_name}"
        module = importlib.import_module(full_module_name)
        modules.append(module)
    return modules
