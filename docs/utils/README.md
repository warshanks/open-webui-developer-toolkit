# Utilities Overview

This folder tracks key helper modules found under `backend/open_webui/utils/` in
the upstream project.  The utilities underpin almost every route in Open WebUI,
from authentication to model selection.  Each file implements a slice of the
server logic.  The most commonly used modules are summarised below – follow the
links for in‑depth notes.

| File | Purpose |
|------|---------|
|[plugin.py](plugin.md)|Loads extension modules (pipes, tools and filters) from the database and rewrites their imports.|
|[filter.py](filter.md)|Provides a pipeline system for mutating requests/responses via inlet/outlet hooks.|
|[chat.py](chat.md)|Routes chat completions to OpenAI, Ollama or custom pipes and streams the result.|
|[payload.py](payload.md)|Normalises request bodies and converts OpenAI style payloads to other formats.|
|[tools.py](tools.md)|Discovers tool modules and builds OpenAI compatible JSON specs.|
|[task.py](task.md)|Creates prompts for background tasks and selects the model used for them.|
|[models.py](models.md)|Merges built‑in models, Ollama models and user presets into a single list.|
|[middleware.py](middleware.md)|Orchestrates the entire chat pipeline – payload processing, model invocation and response handling.|
|[auth.py](auth.md)|Password hashing, JWT handling and license utilities.|
|[oauth.py](oauth.md)|Implements OAuth provider login and group synchronisation.|
|[access_control.py](access_control.md)|Group based permission checks used across the API.|
|[misc.py](misc.md)|Assorted helpers such as message utilities and string parsers.|
|[redis.py](redis.md)|Connection helpers and convenience classes backed by Redis.|
|[code_interpreter.py](code_interpreter.md)|Executes Python code in a Jupyter kernel for the code interpreter feature.|
