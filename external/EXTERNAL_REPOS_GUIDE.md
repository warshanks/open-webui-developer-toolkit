# External Repositories Guide

This directory (`external/`) contains external source code repositories directly embedded into our project for easy reference and analysis.

## Current External Repositories:
- **OpenWebUI Source**
    Path: `external/open-webui/`
    URL: [https://github.com/open-webui/open-webui](https://github.com/open-webui/open-webui)

### Purpose:
The OpenWebUI repository is embedded here to allow easy navigation, analysis, and reverse-engineering of its internal source code. It provides direct reference and context for our custom functions and tools.

### How to Update:
A GitHub workflow (`.github/workflows/update-open-webui.yml`) is configured to regularly synchronize this embedded repository with the upstream main branch.

### Usage by AI Agents:
AI agents should explore the embedded OpenWebUI source directly in:
external/open-webui/
for deeper understanding, detailed inspection, or reverse-engineering tasks.
