# OpenAI Responses File Upload

This note outlines the plan for a companion filter that will manage file uploads when using the OpenAI Responses manifold.

## Goals
- Disable WebUI's built-in file handler.
- Upload files directly to OpenAI's API before the request reaches the manifold.
- Persist file references in the chat record for later retrieval.

The implementation will convert image uploads to file objects when required. The exact API endpoints and storage format are still under evaluation.
