# Functions Guide

This directory groups reusable **pipes** and **filters** for Open WebUI. Both are
lightweight Python modules that can be copy–pasted into a WebUI instance.

- **Pipes** transform or generate chat messages. They can call external APIs
  and emit new output.
- **Filters** inspect or modify existing messages. Filters run before and after
  a pipe to change its behaviour.

Each subfolder contains a dedicated guide:

- [`pipes/README.md`](pipes/README.md) – how to implement and use
  pipes.
- [`filters/README.md`](filters/README.md) – how to implement and
  use filters.

Requests pass through filters first and then your pipe. Filters can mutate the
incoming message or the pipe's response, while the pipe generates the final
answer and may invoke tools. Place new modules in the matching subfolder so the
WebUI loader can discover them.
