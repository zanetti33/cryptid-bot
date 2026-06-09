#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker non trovato nel PATH" >&2
  exit 1
fi

echo "[ok] docker trovato: $(docker --version)"

docker compose version >/dev/null 2>&1
printf '[ok] docker compose trovato: '
docker compose version --short

if docker info --format '{{json .Runtimes}}' | grep -q 'nvidia'; then
  echo "[ok] runtime NVIDIA disponibile"
else
  echo "[warn] runtime NVIDIA non rilevato (training CUDA potrebbe non funzionare)"
fi

echo "[ok] validazione compose (profile: dev)"
docker compose --profile dev config >/dev/null


