# Development

## Fixture-first setup

Requirements: Python 3.10+, Node.js 18+, npm, and `just`. From the repository root:

```bash
just setup
cp project/backend/.env.example project/backend/.env
```

Keep `SEARCH_PROVIDER=fixture` for offline development. Authentication and persistent user data need the existing Google/JWT/database configuration. SerpApi, local llama.cpp, and model weights are optional.

## Commands

```bash
just dev          # backend, frontend, model server
just backend
just frontend
just model-server # generic and legacy model routes; models load on first use
just migrate      # uses ALEMBIC_DATABASE_URL, never silently NEON_DB_URL
just lint
just typecheck
just test
just test-e2e
just eval
just smoke
just check
```

The fixture test suite does not need a database or GPU model. `just setup` installs the lightweight POSE v2 runtime/dev packages plus npm dependencies without downloading Playwright browser binaries. Browser automation requires `cd project/frontend && npx playwright install chromium` once. `just test` runs Python unit tests plus Vitest; `just test-e2e` runs the fixture pipeline/API integration tests plus Playwright browser checks against a dedicated development harness.

## Database migration

For a disposable empty local database, set `ALEMBIC_DATABASE_URL` and run `just migrate`. Revision `0001_baseline` is an empty-database baseline; do not stamp it onto an existing legacy database. Revision `0002_generic_search` only adds generic search tables and enables pgvector. Back up a real database and review generated SQL before migration.

## Local models

Set `GPU_SERVER_URL=http://localhost:8001`, `EMBEDDING_MODEL=BAAI/bge-m3`, and `RERANKER_MODEL=BAAI/bge-reranker-v2-m3`. Start `just model-server`. The first embedding/rerank request loads weights and may download them. Without a model server, the backend uses deterministic fallback vectors and no cross-encoder score.

For LLM intent parsing, start a local llama.cpp OpenAI-compatible server and set `LLM_BASE_URL`, optional `LLM_MODEL`, and optional `LLM_API_KEY`. Structured JSON parsing is validated through `SearchIntent`; any transport or output error falls back to deterministic parsing.

## Smoke checks and external services

`just smoke` runs one fixture search and asserts a completed response without API keys. Real SerpApi and real-model smoke tests are intentionally opt-in and require configured local credentials/services. Do not put secrets in test output.
