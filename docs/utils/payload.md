# payload.py

Utility helpers found in `backend/open_webui/utils/payload.py` normalize user supplied parameters.

Key routines:
- `apply_model_params_to_body_openai` and `apply_model_params_to_body_ollama` cast parameter types and rename fields.
- `apply_model_system_prompt_to_body` inserts the model's system prompt, performing variable substitution when metadata is provided.
- Converters to and from Ollama's message format are also defined.
