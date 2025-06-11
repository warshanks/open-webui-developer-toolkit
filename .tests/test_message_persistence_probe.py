from importlib import import_module


def test_importable():
    mod = import_module('functions.pipes.message_persistence_probe.message_persistence_probe')
    assert hasattr(mod, 'Pipe')
