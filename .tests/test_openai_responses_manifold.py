from importlib import import_module
import sys

try:
    import orjson  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - not packaged during tests
    sys.modules["orjson"] = object()

def test_importable():
    mod = import_module('functions.pipes.openai_responses_manifold.openai_responses_manifold')
    assert hasattr(mod, 'Pipe')


def test_encode_decode_roundtrip():
    mod = import_module('functions.pipes.openai_responses_manifold.openai_responses_manifold')

    sample_id = "01HX4Y2VW5VR2Z2HDQ5QY9REHB"
    encoded = mod.encode_id(sample_id)
    assert mod.decode_id(encoded) == sample_id


def test_split_and_extract_ids():
    mod = import_module('functions.pipes.openai_responses_manifold.openai_responses_manifold')

    ids = [
        "01HX4Y2VW5VR2Z2HDQ5QY9REHB",
        "01HX4Y2VW6B091XE84F5G0Z8NF",
    ]
    encoded = "".join(mod.encode_id(i) for i in ids)
    content = f"prefix {encoded} suffix"

    assert mod.extract_encoded_ids(content) == ids

    segments = mod.split_content_by_encoded_ids(content)
    assert segments[0]["type"] == "text"
    assert segments[1]["type"] == "encoded_id"
    assert segments[1]["id"] == ids[0]
    assert segments[2]["type"] == "encoded_id"
    assert segments[2]["id"] == ids[1]
    assert segments[3]["type"] == "text"
