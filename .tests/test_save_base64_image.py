from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import base64
import sys
import types


def _load_pipeline():
    path = Path(__file__).resolve().parents[1] / "functions" / "pipes" / "openai_responses_api_pipeline.py"
    spec = spec_from_file_location("openai_responses_api_pipeline", path)
    mod = module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod

def test_save_base64_image_accepts_dict(monkeypatch, dummy_chat):
    pipeline = _load_pipeline()

    captured = {}

    def dummy_upload(request, meta, data, content_type, user):
        captured['data'] = data
        captured['content_type'] = content_type
        return "url"

    def dummy_load(b64_str):
        captured['b64'] = b64_str
        return b'x', 'image/png'

    monkeypatch.setitem(sys.modules, 'open_webui', types.ModuleType('open_webui'))
    monkeypatch.setitem(sys.modules, 'open_webui.routers', types.ModuleType('open_webui.routers'))
    images_mod = types.ModuleType('open_webui.routers.images')
    images_mod.upload_image = dummy_upload
    images_mod.load_b64_image_data = dummy_load
    monkeypatch.setitem(sys.modules, 'open_webui.routers.images', images_mod)

    b64 = base64.b64encode(b'x').decode()
    out = pipeline.save_base64_image({'b64_json': b64}, None, {})

    assert out == 'url'
    assert captured['data'] == b'x'
    assert captured['b64'] == b64

