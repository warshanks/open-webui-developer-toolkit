# Instruction Injection Valves

The `openai_responses` pipeline supports two optional valves that enrich the system prompt.

* **INJECT_CURRENT_DATE** – when set to `True` the current date is appended at the end of the system instructions. Example output:

```
[existing system prompt]

Today's date: Thursday, May 21, 2025
```

* **INJECT_USER_INFO** – when enabled the user's name and email are appended. If request data is available, a short `device_info` line is also added summarising the client platform and browser. This information is marked as context only.

```
user_info: Justin Kropp <jkropp@glcsolutions.ca>
device_info: Desktop | Windows | IP: 207.194.4.18 | Browser: Edge 136

Note: `user_info` and `device_info` provided solely for AI contextual enrichment.
```
