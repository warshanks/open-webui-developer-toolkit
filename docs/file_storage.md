# File Storage in Open WebUI

Open WebUI stores uploaded files and images under a configurable **data directory**. Understanding this layout is useful when writing extensions or debugging tools.

## Directories

`open_webui.env` defines the base paths. When the backend initialises it resolves `DATA_DIR` and creates folders for uploads and cache:

```
DATA_DIR = Path(os.getenv("DATA_DIR", BACKEND_DIR / "data")).resolve()
...
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
```

Files uploaded by users or created by tools are written to `UPLOAD_DIR` unless a cloud provider is configured. The `STORAGE_PROVIDER` environment variable selects one of four backends:

- `local` – store files directly under `UPLOAD_DIR`
- `s3` – upload to Amazon S3 (and keep a local copy)
- `gcs` – Google Cloud Storage
- `azure` – Azure Blob Storage

Local paths remain the same regardless of provider; remote locations mirror the same file names.

## Database Entries

Metadata for each file is stored in the `file` table (see `open_webui.models.files`). Important columns include:

- `id` – unique identifier (UUID)
- `filename` – original name
- `path` – storage path (local or cloud URI)
- `meta` – JSON blob containing `name`, `content_type`, `size` and optional data

## Upload API

The `/api/v1/files` router exposes CRUD operations. `upload_file()` saves the binary via the selected storage provider and creates the database record. Downloading a file goes through `/api/v1/files/{id}/content` which resolves the path and returns the data.

Generated images use the same API. `images.py` decodes the image data returned by the generation engine and calls `upload_file()`. Chat.svelte receives a message like:

```json
{
  "chat_id": "...",
  "message_id": "...",
  "data": {
    "type": "files",
    "data": {
      "files": [{"type": "image", "url": "/api/v1/files/<id>/content"}]
    }
  }
}
```

## Importing Functions

Custom pipes, filters and tools can be uploaded using the helper script `.scripts/publish_to_webui.py`. It sends the code to `/api/v1/functions/create` and activates the plugin. Example:

```bash
WEBUI_URL=http://localhost:8080 \
WEBUI_KEY=sk-... \
python .scripts/publish_to_webui.py functions/pipes/my_pipe.py
```

When your function needs to attach files it can emit a `chat:message:files` event with URLs returned by the Files API. The toolkit's `__event_emitter__` helper handles this for you.
