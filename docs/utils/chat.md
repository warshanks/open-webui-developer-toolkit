# chat.py

`backend/open_webui/utils/chat.py` coordinates chat completions across multiple sources.

Highlights:
- Chooses between OpenAI, Ollama or a custom pipe based on the selected model.
- Applies inlet/outlet filters through `routers.pipelines` when configured.
- Provides `generate_direct_chat_completion` and `generate_chat_completion` helpers used by the HTTP routes.
