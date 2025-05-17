from pathlib import Path
from urllib.error import HTTPError

import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scripts.publish_to_webui import (
    _detect_type,
    _extract_metadata,
    _build_payload,
    _post,
)


class PublishTests(unittest.TestCase):
    def test_detect_type_from_path(self):
        self.assertEqual(
            _detect_type(Path("src/openwebui_devtoolkit/pipes/tool.py"), None),
            "pipe",
        )
        self.assertEqual(_detect_type(Path("any/filters/foo.py"), None), "filter")
        self.assertEqual(_detect_type(Path("toolz/tools/x.py"), None), "tool")
        self.assertEqual(_detect_type(Path("some/other/path.py"), "filter"), "filter")

    def test_extract_metadata_success(self):
        code = "id: test\ndescription: cool plugin\nprint(1)"
        pid, desc = _extract_metadata(code)
        self.assertEqual(pid, "test")
        self.assertEqual(desc, "cool plugin")

    def test_extract_metadata_missing_id(self):
        with self.assertRaises(ValueError):
            _extract_metadata("description: nope")

    def test_build_payload_structure(self):
        payload = _build_payload("pid", "pipe", "code", "desc")
        self.assertEqual(payload["id"], "pid")
        self.assertEqual(payload["type"], "pipe")
        self.assertEqual(payload["content"], "code")
        self.assertEqual(payload["meta"]["description"], "desc")

    def test_post_success(self):
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
        self.assertEqual(status, 201)

    def test_post_http_error(self):
        def mock_urlopen(req, timeout=30):
            raise HTTPError(req.full_url, 400, "oops", hdrs=None, fp=None)

        with patch("scripts.publish_to_webui.urlopen", mock_urlopen):
            status = _post("http://x", "k", "/create", {"a": 1})
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()

