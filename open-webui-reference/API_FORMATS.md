# API Formats

The backend API primarily exchanges JSON payloads. Requests to a pipe look like:

```json
{
  "chat_id": "123",
  "message": "hello"
}
```

Responses from the pipe are returned as:

```json
{
  "message": "hi there"
}
```

Additional fields may be present depending on the tool and event systems.
