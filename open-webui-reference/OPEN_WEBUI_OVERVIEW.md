# Open WebUI Overview

This folder contains notes about the upstream Open WebUI project. It is a read-
only reference that explains the high-level architecture so extension authors
can understand how their code plugs in.

Open WebUI is structured as a FastAPI backend with a React front end. The
backend exposes chat pipelines, an event system and a tool registry used by the
UI.
