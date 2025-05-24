# Writing **Tools** for Open WebUI

*A practical guide for first-time authors (human **and** AI).*  

---

## Table of Contents
1. [Why Tools?](#why-tools)
2. [Quick Start](#quick-start)
3. [Anatomy of a Tool](#anatomy-of-a-tool)  
   3.1  [Metadata Block](#metadata-block)  
   3.2  [The `Tools` Class](#the-tools-class)  
   3.3  [Defining Tool Methods](#defining-tool-methods)  
4. [Field Reference](#field-reference)
5. [Execution Lifecycle](#execution-lifecycle)
6. [Valves & UserValves](#valves--uservalves)
7. [Default vs Native Mode](#default-vs-native-mode)
8. [EventEmitter Patterns](#eventemitter-patterns)
9. [Testing Your Tool](#testing-your-tool)
10. [Publishing & Distribution](#publishing--distribution)
11. [Example Gallery](#example-gallery)
12. [Troubleshooting Checklist](#troubleshooting-checklist)
13. [Glossary](#glossary)
14. [TODO / Future Research](#todo--future-research)

---

## Why Tools? <a id="why-tools"></a>

Tools give an LLM real-world abilities—live data, external APIs, file I/O, etc.  
When Open WebUI loads a tool it **parses the method docstrings to build a
JSON schema**. That schema is sent to the model so it knows when to call your
code and what arguments to provide. In “Native” mode the model can even
*chain* multiple tools in a single turn. 

---

## Quick Start <a id="quick-start"></a>

Create `functions/tools/my_weather.py`:

```python
"""
name: weather
description: Get the current temperature for a city.
"""

from typing import Dict
import httpx

class Tools:
    async def weather(self, city: str) -> Dict[str, str]:
        """
        name: weather
        description: Returns the current temperature for the given city.
        parameters:
          type: object
          properties:
            city:
              type: string
              description: Name of the city (e.g. "Paris")
          required: [city]
        returns:
          type: object
          properties:
            location: {type: string}
            temperature_c: {type: number}
        """
        r = httpx.get(f"https://wttr.in/{city}?format=j1").json()
        return {
            "location": r["nearest_area"][0]["areaName"][0]["value"],
            "temperature_c": float(r["current_condition"][0]["temp_C"]),
        }
```

Enable the tool for your model (Workspace → Models → Tools) and ask:

> “What’s the temperature in Paris?”

The LLM will trigger `weather()` and include the result in its reply.

---

## Anatomy of a Tool <a id="anatomy-of-a-tool"></a>

### 1  Metadata Block <a id="metadata-block"></a>

A *top-level multi-line string* (or YAML front-matter) can declare file-wide
defaults—handy when your file exports many tool functions.

```python
"""
author: Jane Dev
version: 0.1.0
license: MIT
requirements: httpx
"""
```

Packages listed in `requirements` are auto-installed when the tool is first
imported.

### 2  The `Tools` Class <a id="the-tools-class"></a>

Open WebUI looks for a class literally named `Tools`.
Each *public method* (no leading `_`) is exposed as a callable tool.

```python
class Tools:
    def say_hi(self) -> str:
        """name: hello | description: Return a friendly greeting."""
        return "👋 Hi from Open WebUI!"
```

Methods can be **sync or async**. Async is recommended for I/O.

### 3  Defining Tool Methods <a id="defining-tool-methods"></a>

* **Docstring → JSON Schema**
  Use the “single-line header + YAML block” pattern shown above.
  Required keys:

| Key           | Purpose                                   |
| ------------- | ----------------------------------------- |
| `name`        | Unique identifier seen by the LLM.        |
| `description` | One-line summary; must start with a verb. |
| `parameters`  | JSON Schema describing inputs.            |
| `returns`     | *(Optional)* JSON Schema for outputs.     |

If `returns` is omitted, the result is treated as an arbitrary string.

Example with required and optional args:

```python
    def news(self, topic: str, limit: int = 5) -> list[dict]:
        """
        name: headlines
        description: Fetch top news headlines for a topic.
        parameters:
          type: object
          properties:
            topic:  {type: string, description: Search phrase}
            limit:  {type: integer, description: Max results, default: 5}
          required: [topic]
        returns:
          type: array
          items:
            type: object
            properties:
              title:   {type: string}
              url:     {type: string, description: Original article}
        """
```

---

## Field Reference <a id="field-reference"></a>

| Field             | Type   | Notes                                     |
| ----------------- | ------ | ----------------------------------------- |
| `name`            | string | Must be *unique* across all loaded tools. |
| `description`     | string | Starts with a verb; ≤ 100 chars is ideal. |
| `parameters.type` | string | Usually `"object"`.                       |
| `.properties`     | object | Keys become argument names.               |
| `.required`       | array  | List of mandatory properties.             |
| `returns`         | object | JSON Schema describing return value.      |

> **Tip:** stick to primitives (`string`, `number`, `boolean`, `array`, `object`) so more models can reason about your schema.

---

## Execution Lifecycle <a id="execution-lifecycle"></a>

1. **Import** – File is loaded, deps installed, `Tools()` instantiated once.
2. **Schema Build** – Docstrings parsed → tool JSON appended to model prompt.
3. **Chat** – LLM decides to call tool (native) *or* returns a text trigger (default).
4. **Invoke** – Open WebUI locates method, injects args, awaits result.
5. **Return** – Result inserted into assistant message (or streamed).

---

## Valves & UserValves <a id="valves--uservalves"></a>

Tools can expose configuration using Pydantic models:

```python
from pydantic import BaseModel

class Valves(BaseModel):
    api_key: str
    base_url: str = "https://api.example.com"

class UserValves(BaseModel):
    default_city: str | None = None
```

Declare them at module scope; Open WebUI will hydrate instances and pass them
to every method that accepts a `valves` or `__user__` parameter.

---

## Default vs Native Mode <a id="default-vs-native-mode"></a>

| Mode        | Trigger style                               | Best for                                               |
| ----------- | ------------------------------------------- | ------------------------------------------------------ |
| **Default** | Prompt template (“Use the *weather* tool…”) | Any model, but slower / less precise                   |
| **Native**  | OpenAI-style function calling               | GPT-4o, GPT-3.5-1106, etc. for fast, multi-tool chains |

Switch modes per chat: **Chat ⚙ Controls → Advanced Params → Function Calling**.

---

## EventEmitter Patterns <a id="eventemitter-patterns"></a>

If your method accepts `__event_emitter__`, you can push custom events. The helper is asynchronous and expects a `{type, data}` payload:

```python
async def download(self, url: str, __event_emitter__):
    await __event_emitter__({"type": "status", "data": {"percent": 0}})
    ...
    await __event_emitter__({"type": "status", "data": {"percent": 100}})
    return "Download complete!"
```

Need user interaction? Use `__event_call__`:

```python
result = await __event_call__({
    "type": "confirmation",
    "data": {"title": "Proceed?", "message": "Start download?"}
})
```

Common event types include `status`, `chat:message:delta`, `chat:title`,
`notification`, `confirmation`, `input`, and `execute`.

---

## Testing Your Tool <a id="testing-your-tool"></a>

```python
from importlib import import_module, reload
tool_mod = reload(import_module("functions.tools.my_weather"))
tools = tool_mod.Tools()
assert asyncio.run(tools.weather("Paris"))["location"] == "Paris"
```

For end-to-end tests call `open_webui.utils.chat.generate_chat_completion`
with `tools=[{"spec":..., "callable": ...}]`.

---

## Publishing & Distribution <a id="publishing--distribution"></a>

1. Add a semantic version and `license` to your metadata block.
2. Push to GitHub.
3. Submit to the **Community Tool Library**.
4. Users click **“Import to WebUI”** → Done!

---

## Example Gallery

Sample tool files will be added in a future update.

---

## Troubleshooting Checklist <a id="troubleshooting-checklist"></a>

* Tool not listed? File name must end with `.py`, class must be `Tools`.
* Native calls ignored? Verify model supports function calling **and** mode is *Native*.
* JSON parse errors? Ensure arguments are valid JSON and match your schema.
* Import crash? Check `requirements` spelling—packages install at runtime.

---

## Glossary <a id="glossary"></a>

| Term             | Meaning                                        |
| ---------------- | ---------------------------------------------- |
| **Tool**         | A callable Python function exposed to the LLM. |
| **Valves**       | Admin-level persistent settings for a tool.    |
| **UserValves**   | Per-user settings surfaced in the chat UI.     |
| **EventEmitter** | Callback for sending UI events mid-execution.  |
| **Native Mode**  | OpenAI-style function calling pipeline.        |

---

## TODO / Future Research <a id="todo--future-research"></a>

* **Security Best Practices:** sandboxing, network policies, secrets.
* **Tool Chaining Agents:** design patterns for multi-step reasoning.
* **Typed Returns:** auto-generate Pydantic models from `returns` schema.

