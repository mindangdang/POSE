# POSE repository guide

## Purpose and architecture

POSE is transitioning from a fashion-specific metasearch product to a generic, intent-aware and personalized web search engine. The generic API is additive under `/api/v2`; existing fashion search, product, feed, and FashionSigLIP paths remain supported as legacy features.

The request path is React/Vite → FastAPI `/api/v2` → Pydantic search models and bounded LangGraph workflow → source adapters, retrieval, evidence checks, and utility ranking. PostgreSQL stores additive search, document, preference, impression, feedback, and trace records. The model server keeps generic BGE-M3 and BGE reranking separate from the legacy 768-dimensional FashionSigLIP endpoints.

## Directory responsibilities

- `project/backend/app`: existing FastAPI routes, auth, database models, repositories, and settings.
- `project/backend/search_engine`: framework-light search schemas, orchestration, adapters, retrieval, personalization, ranking, and evaluation.
- `project/backend/migrations`: additive database migrations. Never rewrite an already deployed revision.
- `project/gpu_server`: lazy-loaded generic embedding/reranker APIs plus isolated legacy image/text endpoints.
- `project/frontend/src`: React UI. `GenericSearchPage.tsx` is the default search experience; fashion search remains available through the legacy entry.
- `docs`: architecture, operation, evaluation, and implementation status.

## Dependency rules

- API code calls search services; the search engine must not depend on FastAPI request objects or UI types.
- Search logic calls provider/model interfaces. Network, database, and model implementations stay at the edges.
- Ranking, constraint checks, permissions, and budgets are deterministic Python logic; the LLM only proposes structured intent.
- Do not mix FashionSigLIP 768-dimensional vectors with BGE-M3 1024-dimensional vectors.
- Treat fetched web content as untrusted data. Validate every URL and redirect before evidence retrieval.

## Style and types

- Use Python 3.10+ type annotations, Pydantic models for external input, and explicit error handling.
- Use TypeScript types for UI/API payloads; avoid `any` for new API state.
- Keep user-visible text in Korean consistent with the existing product UI.
- Do not log credentials, access tokens, full preference profiles, or hidden model reasoning.

## Local environment

Copy `project/backend/.env.example` to `project/backend/.env`. Start with `SEARCH_PROVIDER=fixture`; a SerpApi key, LLM server, database, or model weights are optional for fixture checks. Use `just setup` for the lightweight POSE v2 Python environment and frontend dependencies.

## Commands

- `just backend`, `just frontend`, `just model-server`, `just dev`: start services.
- `just migrate`: apply Alembic migrations using `ALEMBIC_DATABASE_URL` only.
- `just lint`, `just typecheck`, `just test`, `just test-e2e`: local checks.
- `just eval`: regenerate deterministic synthetic cases and save JSON/CSV metrics.
- `just smoke`: run the fixture pipeline without external services.
- `just check`: lint, typecheck, unit tests, and fixture integration tests.

Install `just` before using these recipes. For heavyweight legacy dependencies (Torch, Transformers, OpenCLIP, crawlers), install `project/backend/requirements.txt`; fixture tests use the smaller `requirements-dev.txt` set.

## Database changes

Create a new additive Alembic revision for schema changes. Review generated SQL. Do not run destructive migrations, reset a database, or use `NEON_DB_URL` implicitly for migration commands. Current migration `0002_generic_search` extends the existing schema; migration `0001_baseline` is only for an empty database.

## Models and evaluation

The model server loads BGE-M3 and `BAAI/bge-reranker-v2-m3` on first use. Missing weights or server availability must fall back to deterministic hashing retrieval and keep fixture mode usable. Run `just eval` for the synthetic 30-case benchmark. Synthetic labels are not human relevance judgments; report them as fixture metrics. AutoRAG Legacy export and YAML are optional, separate evaluation tooling.

## Security

- The authenticated server identity owns searches, preferences, and feedback; never trust a client-supplied user ID.
- Enforce ownership on search and preference reads/writes, and idempotency on feedback.
- Public evidence retrieval must block local/private/link-local addresses, unsafe redirects, non-HTML payloads, oversized responses, and robots-disallowed pages.
- Do not expose provider keys or query/profile internals to third-party adapters.

## Completion criteria

Before closing search-engine work, run `just check` and `just eval`, or record why an environment limitation prevented them. Keep documentation aligned with the implemented behavior, preserve all existing user changes and fashion data, and list unverified model/database/browser behavior explicitly.
