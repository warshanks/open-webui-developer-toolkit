# Tool System Explained

Tools are reusable actions that pipes can invoke. The backend exposes a registry
where each tool registers a `spec` and an `invoke()` coroutine. When a pipe
needs to call a tool it looks it up by name and awaits `invoke()` with the
arguments provided by the model.

```python
# registering a tool
registry[spec["name"]] = {"spec": spec, "invoke": invoke}
```

The WebUI frontend displays available tools and shows results returned by the
backend. Tools in this repository live in the `tools/` directory.
