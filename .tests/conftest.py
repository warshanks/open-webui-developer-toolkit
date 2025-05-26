import sys
import types

# Create stubs for open_webui modules used by the pipeline
open_webui = types.ModuleType("open_webui")
models_mod = types.ModuleType("open_webui.models")
chats_mod = types.ModuleType("open_webui.models.chats")

class Chats:
    @staticmethod
    def get_chat_by_id(chat_id):
        return None

chats_mod.Chats = Chats

models_models_mod = types.ModuleType("open_webui.models.models")
class Models:
    @staticmethod
    def get_model_by_id(model_id):
        return None

    @staticmethod
    def update_model_by_id(model_id, model_form):
        return False

class ModelForm:
    def __init__(self, **kwargs):
        pass

class ModelParams:
    def __init__(self, **kwargs):
        pass

models_models_mod.Models = Models
models_models_mod.ModelForm = ModelForm
models_models_mod.ModelParams = ModelParams

utils_mod = types.ModuleType("open_webui.utils")
misc_mod = types.ModuleType("open_webui.utils.misc")

def get_message_list(*args, **kwargs):
    return []

misc_mod.get_message_list = get_message_list
utils_mod.misc = misc_mod

sys.modules.setdefault("open_webui", open_webui)
sys.modules.setdefault("open_webui.models", models_mod)
sys.modules.setdefault("open_webui.models.chats", chats_mod)
sys.modules.setdefault("open_webui.models.models", models_models_mod)
sys.modules.setdefault("open_webui.utils", utils_mod)
sys.modules.setdefault("open_webui.utils.misc", misc_mod)
