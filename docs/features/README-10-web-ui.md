# Feature 10 — Web Workspace

> Backend: `api/api_server.py` · `workspace/webui/index.html`
> CLI: `upf-insight web --port 8585`

## What it does

A local, offline web UI for power-intent validation. No cloud, no EDA tool,
no build step — the API is stdlib-only (`http.server`) and the UI is vanilla
JS.

## Start

```bash
upf-insight web
# opens http://127.0.0.1:8585
```

## API

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/version` | GET | product name + version |
| `/api/rules` | GET | the rule registry |
| `/api/validate` | POST | validate pasted UPF text or file paths |
| `/api/generate` | POST | generate a skeleton into the editor |
| `/` | GET | the workspace page |

## Workspace features (v0.1.0)

- Paste UPF → **Validate** → findings table (rule, severity, file:line,
  message, support) + summary + support boundary.
- **Generate skeleton** button fills the editor.

## Trust boundary

The workspace is a consumer of the backend; it adds no analysis of its own.
Everything runs on `127.0.0.1`; nothing leaves the machine.

## Roadmap

- Model panel (browse domains/supplies/states).
- PST panel.
- Diff panel.
- Dark mode / report export.