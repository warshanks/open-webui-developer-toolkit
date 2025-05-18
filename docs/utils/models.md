# models.py

`backend/open_webui/utils/models.py` aggregates model lists from different sources and adds custom entries.

Features:
- Fetches OpenAI and Ollama model lists.
- Adds function-based pipe models using `functions.get_function_models`.
- Merges custom models stored in the database, preserving pipe and action metadata.
