set shell := ["bash", "-cu"]

frontend_dir := "project/frontend"
backend_dir := "project/backend"
gpu_server_dir := "project/gpu_server"

frontend_port := "3000"
backend_port := "8000"
gpu_server_port := "8001"

default:
  @just --list

setup:
  python3 -m venv .venv && .venv/bin/python -m pip install --upgrade pip && .venv/bin/pip install -r project/backend/requirements-dev.txt && cd {{frontend_dir}} && npm ci --ignore-scripts

dev:
  trap 'kill "$backend_pid" "$model_pid" "$frontend_pid" 2>/dev/null || true' EXIT INT TERM; .venv/bin/python -m uvicorn project.backend.main:app --reload --host 0.0.0.0 --port {{backend_port}} & backend_pid=$!; GPU_SERVER_PORT={{gpu_server_port}} .venv/bin/python -m uvicorn project.gpu_server.main:app --host 0.0.0.0 --port {{gpu_server_port}} & model_pid=$!; cd {{frontend_dir}} && npm run dev -- --host 0.0.0.0 & frontend_pid=$!; wait

frontend:
  cd {{frontend_dir}} && npm run dev -- --host 0.0.0.0

backend:
  BACKEND_PORT={{backend_port}} .venv/bin/python -m uvicorn project.backend.main:app --reload --host 0.0.0.0 --port {{backend_port}}

model-server:
  GPU_SERVER_PORT={{gpu_server_port}} .venv/bin/python -m uvicorn project.gpu_server.main:app --host 0.0.0.0 --port {{gpu_server_port}}

gpu_server:
  just model-server

migrate:
  .venv/bin/python -m alembic -c project/backend/alembic.ini upgrade head

lint:
  .venv/bin/python -m ruff check --select E4,E7,E9,F project/backend/search_engine project/backend/tests/test_pose_v2.py project/backend/app/api/router.py project/backend/app/db/models/search.py project/backend/app/manage/settings.py project/gpu_server/generic_models.py project/gpu_server/generic_routes.py
  cd {{frontend_dir}} && npm run lint

typecheck:
  .venv/bin/python -m mypy --ignore-missing-imports --follow-imports=silent project/backend/search_engine
  cd {{frontend_dir}} && npx tsc --noEmit

test:
  .venv/bin/python -m pytest project/backend/tests -q -m "not integration"
  cd {{frontend_dir}} && npm test

test-e2e:
  .venv/bin/python -m pytest project/backend/tests -q -m integration
  cd {{frontend_dir}} && npm run test:e2e

eval:
  .venv/bin/python -m project.backend.search_engine.evaluation.generate_dataset
  .venv/bin/python -m project.backend.search_engine.evaluation.benchmark

smoke:
  .venv/bin/python -m project.backend.search_engine.smoke

check:
  just lint
  just typecheck
  just test
  just test-e2e

all:
  just dev
