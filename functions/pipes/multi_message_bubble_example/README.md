# Multi-Message Bubble Example

Demonstrates how a pipe can emit more than one assistant message in response to a single user prompt.
After the first response this example prompts the user to confirm whether a second
message should be displayed.

Open WebUI only renders messages that already exist in the chat's history. After
creating an additional message row you must broadcast a `chat:message` event so
the UI learns about it. Without this event the extra row will remain invisible.
