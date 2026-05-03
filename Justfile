set shell := ["bash", "-lc"]

frontend_dir := "project/frontend"
backend_dir := "project/backend"
gpu_server_dir := "project/gpu_server"

frontend_port := "3000"
backend_port := "8000"
gpu_server_port := "8001"

default:
  @just --list

frontend:
  cd {{frontend_dir}} && npm run dev -- --host 0.0.0.0

backend:
  BACKEND_PORT={{backend_port}} uvicorn project.backend.main:app --reload --host 0.0.0.0 --port {{backend_port}}

gpu_server:
  GPU_SERVER_PORT={{gpu_server_port}} uvicorn project.gpu_server.main:app --reload --host 0.0.0.0 --port {{gpu_server_port}}

all:
  trap 'kill 0' SIGINT; just backend & just frontend & just gpu_server & wait