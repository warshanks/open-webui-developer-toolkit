import sys
from pathlib import Path
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.modules.setdefault("httpx", types.ModuleType("httpx"))
dummy_chats_mod = types.ModuleType("open_webui.models.chats")
dummy_chats_mod.Chats = types.SimpleNamespace(get_chat_by_id=lambda _ : None)
sys.modules.setdefault("open_webui", types.ModuleType("open_webui"))
sys.modules.setdefault("open_webui.models", types.ModuleType("open_webui.models"))
sys.modules.setdefault("open_webui.models.chats", dummy_chats_mod)

from openwebui_devtoolkit.pipes.openai_responses_api_pipeline import (  # noqa: E402
    build_responses_payload,
    prepare_tools,
    pretty_log_block,
)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        """Stub ``open_webui.models.chats`` for the tests."""
        dummy_chat = {"history": {"currentId": None, "messages": {}}}

        def get_chat_by_id(_):
            return types.SimpleNamespace(chat=dummy_chat)

        chats_mod = types.ModuleType("open_webui.models.chats")
        chats_mod.Chats = types.SimpleNamespace(get_chat_by_id=get_chat_by_id)
        self.patcher = patch.dict(
            sys.modules,
            {
                "open_webui": types.ModuleType("open_webui"),
                "open_webui.models": types.ModuleType("open_webui.models"),
                "open_webui.models.chats": chats_mod,
                "httpx": types.ModuleType("httpx"),
            },
        )
        self.patcher.start()
        self.chats_patch = patch(
            "openwebui_devtoolkit.pipes.openai_responses_api_pipeline.Chats",
            chats_mod.Chats,
        )
        self.chats_patch.start()
        self.dummy_chat = dummy_chat

    def tearDown(self):
        self.patcher.stop()
        self.chats_patch.stop()

    def test_prepare_tools_variants(self):
        reg = {
            "tools": {
                "one": {
                    "spec": {
                        "name": "foo",
                        "description": "d",
                        "parameters": {"type": "object"},
                    }
                },
                "two": {"spec": {"function": {"name": "bar"}}},
            }
        }
        tools = prepare_tools(reg)
        self.assertEqual(tools[0]["name"], "foo")
        self.assertEqual(tools[1]["name"], "bar")
        self.assertEqual(tools[0]["type"], "function")
        self.assertEqual(tools[1]["type"], "function")

    def test_build_responses_payload(self):
        self.dummy_chat["history"] = {
            "currentId": "m2",
            "messages": {
                "m1": {"role": "user", "content": [{"text": "hi"}], "parentId": None},
                "m2": {
                    "role": "assistant",
                    "content": [{"text": "hello"}],
                    "parentId": "m1",
                },
            },
        }

        payload = build_responses_payload("chat1")
        self.assertEqual(
            payload,
            [
                {"role": "user", "content": [{"type": "input_text", "text": "hi"}]},
                {
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "hello"}],
                },
            ],
        )

    def test_pretty_log_block(self):
        out = pretty_log_block({"a": 1}, label="lbl")
        self.assertIn("lbl =", out)
        self.assertIn('{\n  "a": 1\n}', out)


if __name__ == "__main__":
    unittest.main()
