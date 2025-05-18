# Filters Guide

Filters modify or inspect chat messages before or after a pipe runs. They expose
a `Filter` class with optional `pre_process()` and `post_process()` methods.

```python
class Filter:
    async def pre_process(self, message: str) -> str:
        return message

    async def post_process(self, response: str) -> str:
        return response
```

Place filter modules in this folder. A filter can be combined with any pipe to
alter its input or output.
