#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker CLI was not found. Install Docker Desktop and make sure it is on PATH." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker Desktop is not running. Start it, wait until the engine is ready, then retry." >&2
  exit 1
fi

if [[ ! -f backend/.env ]]; then
  echo "Missing backend/.env. Add the model key and local database settings there, then retry." >&2
  exit 1
fi

docker compose --env-file backend/.env up --build -d
