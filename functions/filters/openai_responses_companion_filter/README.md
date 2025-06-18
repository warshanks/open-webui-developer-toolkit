# OpenAI Responses Companion Filter
The **Companion Filter** works together with the **OpenAI Responses Manifold** (pipe) by disabling Open WebUI’s built-in file handling and prompt injection, ensuring the pipe receives unmodified, original chat data.

> **Author:** [Justin Kropp](https://github.com/jrkropp)  
> **License:** MIT

⚠️ **Pre‑production preview.** The filter is still under early testing and will be fully released as `1.0.0`.

## Installation
1. Copy `openai_responses_companion_filter.py` to your Open WebUI under **Admin Panel ▸ Functions**.  Save it.
2. Enable the filter.
3. Navigate **Admin Panel ▸ Settings ▸ Models**
4. Edit each OpenAI Responses model.  Enable 'OpenAI Responses Companion Filter'.
   
## Why this filter is required

* **Open WebUI** automatically processes file uploads and modifies prompts **before** pipes run.
* **Pipes** run too late to disable this built-in behavior.
* Therefore, a dedicated filter (`file_handler = True`) is required to bypass default behavior.

---

## Responsibilities (Sequential Workflow)

Simple Rule: The filter handles tasks before Open WebUI modifies requests; the pipe handles sending requests to OpenAI and processing responses.

The workflow below clearly defines each responsibility in the order they occur:

| Step | Responsibility                                 | Companion Filter                           | Responses Manifold (Pipe) |
| ---- | ---------------------------------------------- | ------------------------------------------ | ------------------------- |
| 1    | Disable built-in Open WebUI file injection     | ✅                                          | ❌                         |
| 2    | Validate file uploads (size, type, format)     | ✅                                          | ❌                         |
| 3    | Upload files to OpenAI (`/files` endpoint)     | ✅                                          | ❌                         |
| 4    | Store returned OpenAI file IDs in metadata     | ✅                                          | ❌ (uses IDs only)         |
| 5    | Remove raw file uploads from request           | ✅                                          | ❌                         |
| 6    | Construct and send final API request           | ❌                                          | ✅                         |
| 7    | Handle responses (streaming, tools, events)    | ❌                                          | ✅                         |
| 8    | Reconstruct chat history from responses        | ❌                                          | ✅                         |
| 9    | Optional: Modify or post-process response text | ⚠️ (possible via outlet, TBD)               | ✅ (typical approach)      |

* **✅ Responsible** | **❌ Not responsible** | ⚠️ **Optional**

---

## Future considerations

* Ensure graceful handling of missing, invalid, or expired file IDs.
* Consider asynchronous uploads or chunking of large files.

## Installation

Copy `openai_responses_companion_filter.py` into Open WebUI under:

**Admin ▸ Filters**