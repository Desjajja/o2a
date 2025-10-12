# Repository Guidelines

## Project Structure & Module Organization
- `proxy/` holds the FastAPI proxy; `proxy/main.py` wires routing, auth, and streaming translators living under `proxy/translators/` and `proxy/providers/`.
- `ui/` contains the React admin console with pages in `ui/src/pages/`, shared UI in `ui/src/components/`, and data hooks in `ui/src/services/`.
- `config/` keeps JSON schemas and default routing tables; never store secrets here.
- `tests/` mirrors runtime modules (`tests/proxy/`, `tests/ui/`) with shared fixtures in `tests/fixtures/`.
- `doc/` houses design references like `doc/api_migration.md` and should change alongside architecture updates.

## Build, Test, and Development Commands
- `uv sync` installs Python dependencies declared in `pyproject.toml`.
- `uv run uvicorn proxy.main:app --reload --port 8082` runs the proxy locally with live reload.
- `npm install --prefix ui` prepares UI tooling; `npm run dev --prefix ui` serves the admin console.
- `uv run pytest` executes backend unit and integration tests; use `-k streaming` to narrow focus.
- `npm test --prefix ui` runs component tests; `npm run cy:run --prefix ui` covers end-to-end flows.

## Coding Style & Naming Conventions
- Python 3.11: 4-space indent, snake_case functions, PascalCase classes; run `uv run ruff format` then `uv run ruff check` before commits.
- TypeScript/React: camelCase variables/hooks, PascalCase components, colocate styles as `.module.css`; enforce with `npm run lint --prefix ui`.
- Config JSON: keep snake_case keys consumed in code and document overrides in `config/README.md`.

## Testing Guidelines
- Name backend tests `test_<feature>.py`; mock upstream OpenAI calls with `httpx.MockTransport` fixtures.
- Assert streaming order using async helpers in `tests/proxy/streaming_utils.py` and snapshot Anthropic payloads where practical.
- UI specs end with `.spec.tsx` and live beside components; Cypress suites reside in `tests/ui/e2e/`.
- Target ≥85% coverage on proxy and ≥80% on UI; fail CI if thresholds drop.

## Commit & Pull Request Guidelines
- Keep commit summaries ≤72 chars in present tense, e.g., `Proxy: add SSE delta adapter`, and note tests in the body.
- Rebase onto `main` before opening a PR and squash fixups locally.
- PRs should state intent, testing, config impacts, and attach screenshots for UI changes; link issues with `Fixes #123`.
- Request both backend and UI reviewers when touching shared areas.

## Security & Configuration Tips
- Provide provider keys via environment variables or a secrets manager; keep `.env` out of git.
- After editing config, run `uv run scripts/check_config.py` to validate required fields and mappings.
- Rotate credentials and guard the admin UI with `AUTH_BASIC_*` variables when sharing demos.
