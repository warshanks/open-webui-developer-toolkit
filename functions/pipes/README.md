# Pipes Guide

A **pipe** is a single Python file that exposes a `Pipe` class. Open WebUI loads
these modules dynamically and executes the pipe when a user selects it as a chat
model.

```python
# minimal pipe structure
class Pipe:
    async def pipe(self, chat_id: str, message: str) -> str:
        return "response"
```

Pipes may call external APIs, emit new chat messages and manage their own state.
To add a new pipe place the file here and ensure it defines a `Pipe` class with
an async `pipe()` method.
