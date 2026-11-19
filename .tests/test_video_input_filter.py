import base64
from types import SimpleNamespace

import pytest

from functions.filters.video_input_filter import video_input_filter as mod

USER = {"id": "u1"}


@pytest.fixture
def files(tmp_path, monkeypatch):
    """In-memory Files table backed by real files on disk."""
    table = {}

    def add(file_id, data=b"video-bytes", user_id="u1", content_type="video/mp4", name="clip.mp4"):
        path = tmp_path / f"{file_id}_{name}"
        path.write_bytes(data)
        table[file_id] = SimpleNamespace(
            id=file_id, user_id=user_id, filename=name, path=str(path),
            meta={"name": name, "content_type": content_type, "size": len(data)},
        )

    async def get_file_by_id(file_id):
        return table.get(file_id)

    monkeypatch.setattr(mod.Files, "get_file_by_id", staticmethod(get_file_by_id))
    return add


def tag(file_id, content_type="video/mp4"):
    return (
        f'<attached_files>\n<file type="file" id="{file_id}" url="{file_id}" '
        f'content_type="{content_type}" name="clip.mp4"/>\n</attached_files>\n\n'
    )


def video_part(data=b"video-bytes", content_type="video/mp4"):
    url = f"data:{content_type};base64,{base64.b64encode(data).decode()}"
    return {"type": "video_url", "video_url": {"url": url}}


async def test_attaches_videos_to_the_messages_that_referenced_them(files):
    files("v1", b"first")
    files("v2", b"second")
    body = {"messages": [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": tag("v1") + "explain this"},
        {"role": "assistant", "content": "sure"},
        {"role": "user", "content": [{"type": "text", "text": tag("v2") + "and this?"}]},
    ]}
    out = await mod.Filter().inlet(body, __user__=USER)
    first, last = out["messages"][1]["content"], out["messages"][3]["content"]
    assert first == [{"type": "text", "text": tag("v1") + "explain this"}, video_part(b"first")]
    assert last[-1] == video_part(b"second")
    assert out["messages"][0]["content"] == "sys"


async def test_falls_back_to_current_upload_without_file_tags(files):
    files("v1")
    body = {
        "messages": [{"role": "user", "content": "what happens here?"}],
        "files": [
            {"id": "v1", "type": "file", "content_type": "video/mp4"},
            {"id": "d1", "type": "file", "content_type": "application/pdf"},
        ],
    }
    out = await mod.Filter().inlet(body, __user__=USER)
    assert out["messages"][0]["content"][-1] == video_part()
    assert [f["id"] for f in out["files"]] == ["d1"]


async def test_ignores_non_video_tags_and_other_users_files(files):
    files("theirs", user_id="u2")
    files("doc", content_type="application/pdf")
    content = tag("theirs") + tag("doc", "application/pdf") + "hi"
    body = {"messages": [{"role": "user", "content": content}]}
    out = await mod.Filter().inlet(body, __user__=USER)
    assert out["messages"][0]["content"] == content


async def test_oversized_video_is_replaced_by_a_note(files):
    files("big", b"x" * (2 * 1024 * 1024))
    events = []

    async def emitter(event):
        events.append(event)

    f = mod.Filter()
    f.valves.MAX_VIDEO_MB = 1
    body = {"messages": [{"role": "user", "content": tag("big") + "hi"}]}
    out = await f.inlet(body, __user__=USER, __event_emitter__=emitter)
    note = out["messages"][0]["content"][-1]
    assert note["type"] == "text" and "over the 1 MB limit" in note["text"]
    assert events and events[0]["data"]["type"] == "warning"
