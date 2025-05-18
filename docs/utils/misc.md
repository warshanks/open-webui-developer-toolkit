# misc.py

`backend/open_webui/utils/misc.py` collects a set of helpers used across the server. The functions range from message list utilities to hashing helpers and small parsers.

The module is imported by many other utilities such as `payload.py` and `task.py`.

## Message helpers

Several functions work with OpenAI style message dictionaries. The most common pattern is to search or update the last message of a given role.

```python
messages = [
    {"role": "system", "content": "welcome"},
    {"role": "user", "content": "hi"},
]
add_or_update_system_message("new system", messages)
# -> messages[0]['content'] == 'new system\nwelcome'
```

Key routines:

- `get_message_list(messages, message_id)` – rebuilds the chain of messages using `parentId` links. Useful when a chat is stored in a dictionary by id.
- `get_last_user_message_item` / `get_last_assistant_message_item` – return the most recent item of the requested role.
- `prepend_to_first_user_message_content(content, messages)` – inserts text before the first user message.
- `add_or_update_system_message` / `add_or_update_user_message` / `append_or_update_assistant_message` – modify the first or last message in place depending on the role.

`get_messages_content(messages)` converts a list into a single string labelled by role.

## OpenAI response templates

`openai_chat_message_template` produces the base JSON structure returned by the OpenAI API. `openai_chat_chunk_message_template` and `openai_chat_completion_message_template` build upon it for streaming and final responses respectively.

Example usage:

```python
chunk = openai_chat_chunk_message_template(
    model="gpt-3.5-turbo",
    content="hello",
)
```

These helpers populate the required `id`, `created`, `model` and `choices` fields so callers only need to fill in the dynamic parts.

## Hashing and validation

- `get_gravatar_url(email)` returns the gravatar image URL derived from a SHA‑256 hash of the email address.
- `calculate_sha256(file_path, chunk_size)` streams a file in chunks and computes its hash.
- `calculate_sha256_string(string)` hashes an arbitrary string.
- `validate_email_format(email)` performs a minimal regex check (accepts `@localhost` addresses).
- `sanitize_filename(file_name)` lowercases and strips non‑alphanumeric characters.

## Miscellaneous parsers

`parse_duration(duration)` translates strings like `"1h30m"` into a `timedelta` object. Passing `"-1"` or `"0"` yields `None`.

```python
parse_duration("3h15m")  # -> datetime.timedelta(seconds=11700)
```

`parse_ollama_modelfile(model_text)` extracts parameters from an Ollama `Modelfile`. Fields such as `temperature` or `num_ctx` are converted to the right type and placed under the returned `params` dictionary. The helper also collects any `MESSAGE` entries into a list of message dictionaries.

`convert_logit_bias_input_to_json("32098:-100,1234:50")` converts comma separated `token:bias` pairs to a JSON string accepted by OpenAI style APIs.
