# SPA Recognition (MVP V1)

Questo modulo fornisce:
- backend permissivo in memoria per le fasi `setup`, `map`, `structures`, `clues`, `recalculate`,
- integrazione AI con `infer_hypothesis_space` e `recommend_moves`,
- frontend React minimale per inserimento manuale stato e trigger ricalcolo AI.

## Backend + Frontend (Docker)

Avvio stack sviluppo:

```bash
./scripts/docker/dev.sh
```

Demo CLI senza frontend:

```bash
docker compose --profile dev run --rm backend-dev python -m spa_recognition.backend.demo_runner
```

In sviluppo:
- backend su `http://127.0.0.1:8000`
- frontend su `http://127.0.0.1:5173`

Per stack production-like locale:

```bash
./scripts/docker/prod.sh
```

