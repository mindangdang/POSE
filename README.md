# POSE — Personalized Intent-Aware Search Engine

POSE is evolving from a fashion metasearch product into a generic, intent-aware web search engine. The v2 workflow understands explicit and inferred criteria, retrieves query-relevant user preferences, combines external, sparse, and dense retrieval, checks available evidence, and ranks by user utility. The v2 API and data model are additive; existing fashion search, product/feed, and FashionSigLIP functionality remain available as legacy paths.

## POSE v2 capabilities

- Structured `SearchIntent`, criteria, exclusions, user preferences, and feedback validation with Pydantic.
- Bounded FastAPI and LangGraph workflow with cancellation, query/concurrency/candidate/evidence budgets, and one deterministic refinement pass.
- Google Organic SerpApi and offline fixture source adapters; BM25, BGE-M3 or deterministic hashing dense retrieval, and weighted RRF.
- Hard-constraint filtering, unknown evidence handling, optional public-page verification, optional cross-encoder reranking, and utility ranking.
- Authenticated REST/WebSocket API at `/api/v2`, additive Alembic schema, preference controls, and a generic React search interface.
- Deterministic 30-case synthetic evaluation, B0–B8 baseline harness, JSON/CSV output, and optional AutoRAG Legacy export.

The fixture pipeline runs without external keys or model weights. Synthetic benchmark metrics are not human relevance judgments. The pgvector cache is wired but has not been exercised against a live PostgreSQL database. Automatic criterion-level preference learning, durable event replay, real provider/model evaluation, and production rollout remain follow-up work; see [implementation status](docs/implementation_plan.md).

## Quick start

Requirements: Python 3.10+, Node.js 18+, npm, and `just`.

```bash
just setup
cp project/backend/.env.example project/backend/.env
```

The copied environment defaults to `SEARCH_PROVIDER=fixture`. Start the backend, frontend, and lazy model server together with:

```bash
just dev
```

Useful independent commands:

```bash
just backend
just frontend
just model-server
just smoke
just test
just test-e2e
just eval
just check
```

The local model server downloads BGE weights only on first inference. For local llama.cpp JSON intent parsing, set `LLM_BASE_URL` and optional `LLM_MODEL` in `project/backend/.env`. For external Google Organic search, set `SERPAPI_API_KEY` or `SERP_API_KEY` and `SEARCH_PROVIDER=serpapi`. Without a SerpApi key the pipeline falls back to fixture mode.

## Database

Search data uses an additive migration. Configure `ALEMBIC_DATABASE_URL` explicitly before running:

```bash
just migrate
```

Migration revision `0001_baseline` is only for an empty database. Do not stamp it onto an existing production schema. `0002_generic_search` adds generic search tables without deleting fashion records. Review [development guidance](docs/development.md) before migrating an existing database.

## API

The existing auth system protects search and preference operations. Generic endpoints include:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v2/search` | Start a bounded search; returns `search_id` |
| `GET` | `/api/v2/search/{search_id}` | Read status or recover the result |
| `POST` | `/api/v2/search/{search_id}/clarify` | Add missing context and continue as a new search |
| `POST` | `/api/v2/search/{search_id}/cancel` | Cancel an active search |
| `POST` | `/api/v2/feedback` | Record idempotent feedback on an exposed result |
| `GET/POST` | `/api/v2/preferences` | List or create preferences |
| `PATCH/DELETE` | `/api/v2/preferences/{id}` | Update or delete a preference |
| `WS` | `/api/v2/ws/{search_id}?token=...` | Receive owner-checked stage events |

The model server provides generic `POST /embed`, `POST /embed/batch`, `POST /rerank`, and health endpoints. Legacy FashionSigLIP endpoints remain separate and retain their existing vector dimensions.

## Documentation

- [Architecture](docs/architecture.md)
- [Search pipeline and budgets](docs/search_pipeline.md)
- [Personalization and feedback](docs/personalization.md)
- [Evaluation and AutoRAG](docs/evaluation.md)
- [Development and migrations](docs/development.md)
- [Phased implementation status](docs/implementation_plan.md)
- [Agent/repository instructions](AGENTS.md)

## Legacy fashion experience

The original fashion search and saved-item feed have not been removed. The generic search UI includes a path back to the legacy fashion search. Existing product tables and 768-dimensional FashionSigLIP vectors are not mixed with the new 1024-dimensional BGE-M3 embeddings.
