# oai2ant

Bridge Anthropic-style clients to OpenAI-compatible providers through a FastAPI proxy and an optional React admin console.

## Features
- FastAPI proxy that normalises Anthropic API calls into OpenAI payloads.
- Hot-reload development loop with a single `o2a` CLI command.
- React admin UI for managing provider mappings and testing chat flows.
- Config staging with restart semantics backed by JSON settings.

## Requirements
- Python 3.11+ (managed with [`uv`](https://github.com/astral-sh/uv)).
- Node.js 18+ with npm for the admin UI.
- Optional: modern browser for the UI.

## Installation
```bash
uv sync
source .venv/bin/activate
npm install --prefix ui
# install the CLI into your environment
uv tool install --from . oai2ant
# alternatively: pip install -e .
```

## Quick Start
Start only the proxy (FastAPI + Uvicorn):
```bash
o2a
```
The proxy binds to `http://0.0.0.0:8082` by default. Health checks are exposed at `/health`, while Anthropic-compatible chat routes live under `/v1/messages`.

Start only the admin UI (requires the proxy to already be running):
```bash
o2a --ui
```
If the proxy is unavailable, this command exits with an error. Start `o2a` in another terminal first, then re-run `o2a --ui`. When successful the CLI launches Vite on `http://127.0.0.1:5173` (opening your browser unless `--no-open-browser` is supplied) and keeps the UI running until you press `Ctrl+C`.

## CLI Reference
```text
o2a [--host HOST] [--port PORT] [--reload | --no-reload]
    [--log-level LEVEL]
    [--ui] [--ui-host HOST] [--ui-port PORT]
    [--proxy-host HOST] [--proxy-port PORT]
    [--open-browser | --no-open-browser]
```
- `--host` / `--port`: customise FastAPI bind address (defaults `0.0.0.0:8082`).
- `--reload` / `--no-reload`: toggle autoreload (default enabled).
- `--log-level`: set Uvicorn log level (`info` by default).
- `--ui`: launch only the React admin console (fails if the proxy is offline).
- `--ui-host` / `--ui-port`: override UI bind address (`127.0.0.1:5173` by default).
- `--open-browser`: automatically open the UI when `--ui` is used (disable with `--no-open-browser`).
- `--proxy-host` / `--proxy-port`: target proxy health endpoint when `--ui` is used (`127.0.0.1:8082` by default).

## Configuration
Provider settings live in `config/settings.json` and follow the schema enforced by `ProxyConfig`. Use the UI to stage changes or edit the file manually, then trigger a restart via `/admin/restart` or the UI button.

When running outside development, set required secrets through environment variables (for example `AUTH_BASIC_USER`, `AUTH_BASIC_PASS`, and upstream API keys).

## Development Workflow
- Run the proxy with `o2a` (or `uv run uvicorn proxy.main:app --reload --port 8082`).
- Iterate on the admin UI with `o2a --ui` or `npm run dev --prefix ui`.
- Format and lint Python code via `uv run ruff format` and `uv run ruff check`.
- Lint UI code with `npm run lint --prefix ui`.

## Testing
- Backend: `uv run pytest` (use `-k streaming` to focus streaming tests).
- Frontend unit tests: `npm test --prefix ui`.
- Cypress end-to-end: `npm run cy:run --prefix ui`.

## Troubleshooting
- `ECONNREFUSED` errors from the UI usually mean the proxy isn’t running—restart with `o2a`.
- `o2a --ui` exiting immediately indicates the proxy health check failed; ensure `o2a` is running in another terminal and reachable at `http://127.0.0.1:8082/health`.
- If `npm run dev` fails, confirm Node.js ≥18 and reinstall via `npm install --prefix ui`.
- Uvicorn reload requires `watchfiles`; ensure it is available by reinstalling dependencies with `uv sync`.

## Licensing
This project is provided without an explicit license. Contact the maintainers for usage terms.
