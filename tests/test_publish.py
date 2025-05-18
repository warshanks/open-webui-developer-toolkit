from pathlib import Path
from urllib.error import HTTPError

import pytest
from unittest.mock import patch

from scripts.publish_to_webui import (
    _detect_type,
    _extract_metadata,
    _build_payload,
    _post,
)


def test_detect_type_from_path():
    assert _detect_type(Path("functions/pipes/tool.py"), None) == "pipe"
    assert _detect_type(Path("any/filters/foo.py"), None) == "filter"
    assert _detect_type(Path("toolz/tools/x.py"), None) == "tool"
    assert _detect_type(Path("some/other/path.py"), "filter") == "filter"


def test_extract_metadata_success():
    code = "id: test\ndescription: cool plugin\nprint(1)"
    pid, desc = _extract_metadata(code)
    assert pid == "test"
    assert desc == "cool plugin"


def test_extract_metadata_missing_id():
    with pytest.raises(ValueError):
        _extract_metadata("description: nope")


def test_build_payload_structure():
    payload = _build_payload("pid", "pipe", "code", "desc")
    assert payload["id"] == "pid"
    assert payload["type"] == "pipe"
    assert payload["content"] == "code"
    assert payload["meta"]["description"] == "desc"


def test_post_success():
    class DummyResp:
        def __init__(self, code=200):
            self._code = code

        def getcode(self):
            return self._code

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    def mock_urlopen(req, timeout=30):
        return DummyResp(201)

    with patch("scripts.publish_to_webui.urlopen", mock_urlopen):
        status = _post("http://x", "k", "/create", {"a": 1})
    assert status == 201


def test_post_http_error():
    def mock_urlopen(req, timeout=30):
        raise HTTPError(req.full_url, 400, "oops", hdrs=None, fp=None)

    with patch("scripts.publish_to_webui.urlopen", mock_urlopen):
        status = _post("http://x", "k", "/create", {"a": 1})
    assert status == 400
