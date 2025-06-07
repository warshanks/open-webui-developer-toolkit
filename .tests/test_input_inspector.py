from importlib import import_module


def test_importable():
    mod = import_module('functions.pipes.input_inspector.input_inspector')
    assert hasattr(mod, 'Pipe')
