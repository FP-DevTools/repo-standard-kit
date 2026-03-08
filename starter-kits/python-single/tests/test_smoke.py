import importlib


def test_package_imports() -> None:
    module = importlib.import_module("__PACKAGE_NAME__")
    assert module.__doc__ is not None
