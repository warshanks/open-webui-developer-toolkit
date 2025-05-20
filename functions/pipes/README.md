
Pipes are single Python files that implement a `Pipe` class with a `pipe()`
method.  Optionally they can expose multiple models by defining a
`pipes()` method that returns a list of model descriptors.  Each entry is a
dictionary with `id` and `name` keys and will appear as a separate model in
Open WebUI.

```
class Pipe:
    class Valves(BaseModel):
        MODEL_ID: str = "gpt-4o,gpt-4o-mini"

    def pipes(self):
        models = [m.strip() for m in self.valves.MODEL_ID.split(',') if m.strip()]
        return [{"id": m, "name": f"MyPipe: {m}"} for m in models]
```

When `MODEL_ID` contains multiple comma separated values the pipe becomes a
*manifold*, representing more than one model.
