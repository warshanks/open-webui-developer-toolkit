from importlib import import_module
import sys

try:
    import orjson  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - not packaged during tests
    sys.modules["orjson"] = object()

def test_importable():
    mod = import_module('functions.pipes.openai_responses_manifold.openai_responses_manifold')
    assert hasattr(mod, 'Pipe')
