from importlib import import_module


def test_importable():
    mod = import_module('functions.pipes.multi_message_bubble_example.multi_message_bubble_example')
    assert hasattr(mod, 'Pipe')
