#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "$PROJECT_ROOT"

echo "[info] tentativo training con CUDA"
if docker compose --profile train run --rm trainer-cuda "$@"; then
  echo "[ok] training CUDA completato"
  exit 0
fi

echo "[warn] training CUDA non disponibile, fallback CPU"
docker compose --profile train run --rm trainer-cpu "$@"

