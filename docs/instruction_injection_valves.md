# Instruction Injection Valves

The `openai_responses` pipeline supports two optional valves that enrich the system prompt.

* **INJECT_CURRENT_DATE** – when set to `True` the current date is appended at the end of the system instructions. Example output:

```
[existing system prompt]

Today's date: Thursday, May 21, 2025
```

* **INJECT_USER_INFO** – controls how much user context is appended. Options:
  * `Disabled` – no information added (default).
  * `Username and Email` – adds a `user_info` line with the user's name and email.
  * `Username, Email and IP` – also adds a `device_info` line summarising the
    client platform, browser and IP address. The IP is lazily resolved using
    [ip-api.com](http://ip-api.com) and cached so the approximate location and ISP
    appear on subsequent requests. This information is marked as context only.

Example output when using `Username, Email and IP`:

```
user_info: Justin Kropp <jkropp@glcsolutions.ca>
device_info: Desktop | Windows | IP: 207.194.4.18 - Waterloo, Ontario, Canada (Bell Canada) | Browser: Edge 136

Note: `user_info` and `device_info` provided solely for AI contextual enrichment.
```
