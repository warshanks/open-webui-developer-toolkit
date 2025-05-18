# Event System Explained

Open WebUI emits events to update the UI in real time. The backend uses a simple
event-emitter pattern where listeners subscribe to named events. UI components
listen for events such as `message_created` or `tool_started` to update the
interface.

```python
# emitting an event
emit("message_created", {"chat_id": chat_id, "id": msg_id})
```

Extensions can emit custom events to drive additional UI behaviour.
