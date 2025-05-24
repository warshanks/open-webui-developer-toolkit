This repository provides **extensions (pipes, filters, tools)** for the
[Open WebUI](https://github.com/open-webui/open-webui).

## Repository Structure & Instructions

| Path                               | Purpose                        | What you (or an agent) can do             |
| ---------------------------------- | ------------------------------ | ----------------------------------------- |
| **`functions/pipes/`**             | Single-file **pipes** (Python) | Add new pipe files or fix existing ones   |
| **`functions/filters/`**           | Single-file **filters**        | Add new filter files or fix existing ones |
| **`tools/`**                       | Standalone **tools**           | Add new tool files or fix existing ones   |
| **`.scripts/publish_to_webui.py`** | CLI uploader (keep name)       | Edit only if the WebUI API changes        |
| **`docs/`**                        | Additional internal notes      | Add new or update existing docs           |

**Note**: Use exact filenames if you need to search for references (e.g., `grep -R openai_responses_api_pipeline.py`).

## Upstream Reference (Read-Only)

* The `external/open-webui/` folder mirrors the upstream project. **Do not** modify or commit changes here.

## Testing

* Run linting and tests with:

  ```bash
  nox -s lint tests
  ```

* `nox` adds `src` to `PYTHONPATH`, then runs:

  1. **ruff** for linting
  2. **pytest** for tests

* Fixtures in `.tests/conftest.py` mock out `open_webui` so tests run quickly and remain isolated.

## Documentation

* Each top-level folder has a `README.md` explaining what's inside. **Keep these brief** and updated whenever:

  * You learn something new about how extensions work.
  * Behavior changes.
* For upstream details, update the corresponding `*_GUIDE.md` under `external/`.

## Coding Best Practices

1. **Keep functions small and clear**—avoid unnecessary indirection.
2. **Flatten nested logic** and reduce complexity whenever possible.
3. **Follow KISS** (Keep It Simple, Stupid) and **DRY** (Don’t Repeat Yourself).
4. **Inline variables** if they’re used only once.
5. **Reuse helpers** from the main Open WebUI project whenever possible instead
   of rolling our own versions.

That’s it! Keep everything simple, documented, and well-tested so future agents can dive in quickly.
