# Message Persistence Probe

A simple test pipeline that inserts an extra assistant message into the chat history.
Use it to verify whether database writes performed inside a pipe remain after the
middleware finishes processing a request.

The pipe adds a placeholder message referencing the current message ID. It then
returns a short confirmation string.
