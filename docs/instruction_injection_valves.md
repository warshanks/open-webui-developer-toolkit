# Instruction Injection Valves

The `openai_responses` pipeline supports four optional valves that enrich the system prompt.

* **INJECT_CURRENT_DATE** – when set to `True` the current date is appended at the end of the system instructions. Example output:

```
[existing system prompt]

Today's date: Thursday, May 21, 2025
```

* **INJECT_USER_INFO** – adds a `user_info` line with the user's name and email when enabled.

* **INJECT_BROWSER_INFO** – appends a `browser_info` line summarising the client device type, platform and browser.

* **INJECT_IP_INFO** – adds an `ip_info` line with the client's IP address and location when available. The IP details are lazily resolved using [ip-api.com](http://ip-api.com) and cached for subsequent requests.

Example output when all three context valves are enabled:

```
user_info: Justin Kropp <jkropp@glcsolutions.ca>
browser_info: Desktop | Windows | Browser: Edge 136
ip_info: 207.194.4.18 - Waterloo, Ontario, Canada (Bell Canada)

Note: `user_info`, `browser_info` and `ip_info` provided solely for AI contextual enrichment.
```
