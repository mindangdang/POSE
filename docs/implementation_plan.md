# POSE v2 implementation status

Status reflects code in this checkout; it does not imply production rollout.

| Phase | Status | Evidence and remaining work |
| --- | --- | --- |
| 0 · Audit and harness | Implemented | Existing fashion path and dependencies reviewed; docs, `AGENTS.md`, fixture setup, and additive migration added. The environment did not have the Python/frontend dependencies at first, so they were installed locally before the final checks. `just` itself is unavailable here; the equivalent commands were run directly. |
| 1 · Generic baseline | Implemented for fixture/organic adapters | Typed candidates, SerpApi Organic adapter, fixture corpus, lazy BGE API, BM25, hashing/BGE dense path, weighted RRF, API and UI route exist. PostgreSQL/pgvector document retrieval and embedding cache are wired; a live database run remains unverified. |
| 2 · Intent-aware workflow | Partially implemented | Deterministic/optional JSON LLM parser, Pydantic criteria, LangGraph state, concurrency/deadline/budgets and one deterministic refinement pass exist. There is no general tool registry or checkpoint backend. |
| 3 · Personalization and utility | Partially implemented | Scoped preferences, query-conditioned vectors, cross-encoder interface, evidence checks, constraint-aware ranking, feedback idempotency, and document embedding persistence exist. Automatic attribute learning from explicit corrections and persisted preference embeddings remain incomplete. |
| 4 · Frontend | Implemented and locally validated | Generic search is the default and legacy fashion search remains accessible. Search, polling/WebSocket, clarification, criterion edits, result feedback, preference CRUD, cancellation, and error display are wired. Vitest (2) and Playwright Chromium flows (3) pass; production Vite build and TypeScript check pass. |
| 5 · Evaluation and hardening | Partially implemented and fixture-validated | 30-case synthetic generator, metrics, B0–B8 runner, AutoRAG Legacy adapter/config, security checks, and docs exist. The current fixture run is recorded in `evaluation.md`; labels are not human-validated. AutoRAG runtime, real-provider/model runs, and a live PostgreSQL migration remain unverified. |

## Decisions

- Preserve existing fashion features and 768-dimensional records; add an isolated generic API and 1024-dimensional BGE schema.
- Keep fixture mode deterministic so backend integration and evaluation run without paid APIs.
- Treat missing evidence for hard conditions as unknown and keep those results out of the verified list.
- Do not claim quality lift until a human-reviewed held-out dataset and configured real-model/provider measurements exist.

## Remaining production work

Persist detailed trace spans and resumable event history; add richer typed provider/tool policy abstractions and model-backed refinement; learn preferences from explicit criterion-level corrections with transactional idempotency; and run migrations and cache reads/writes against a disposable PostgreSQL/pgvector database before deployment. Offline Alembic SQL generation and the fake repository pipeline test pass, but they do not replace a live database integration check.
