# Pipeline Explained

Open WebUI processes chat requests through a pipeline of filters and a pipe. A
simplified flow looks like:

```mermaid
sequenceDiagram
    participant User
    participant Filters
    participant Pipe
    User->>Filters: message
    Filters->>Pipe: processed message
    Pipe->>Filters: response
    Filters->>User: final response
```

Filters can transform both the input and output. The pipe generates the main
response and may call tools. Place extension modules in `functions/` so that Web
UI can load them into this pipeline.
