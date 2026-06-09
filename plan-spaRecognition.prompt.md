## Plan: Backlog operativo `spa_recognition`

Definisco un backlog a milestone con stime a punti relativi, focalizzato su MVP logica-first: stato in memoria, mappa 108 esagoni cliccabile, due modalità con UX coerente (Strutture/Clue), `warnings` non bloccanti e ricalcolo AI su bottone. Il piano produce prima la specifica dettagliata e poi implementazione incrementale backend/frontend, mantenendo compatibilità col modello `GameSnapshot` e con l’architettura modulare esistente.

### Steps
1. Redigere M1 (5 pt): specifica completa in [docs/SPA_RECOGNITION_SPEC.md](docs/SPA_RECOGNITION_SPEC.md) con milestone, dipendenze, `warnings`, regole permissive V1.
2. Implementare M2 (13 pt): contratto modulo e stato sessione in [spa_recognition/__init__.py](spa_recognition/__init__.py), [spa_recognition/backend/models.py](spa_recognition/backend/models.py), [spa_recognition/backend/session_store.py](spa_recognition/backend/session_store.py).
3. Implementare M2 (cont.) API permissive in [spa_recognition/backend/api.py](spa_recognition/backend/api.py) con `POST /setup`, `/map`, `/structures`, `/clues`, `/recalculate`.
4. Implementare M3 (13 pt): UI React minimale in [spa_recognition/frontend/src](spa_recognition/frontend/src) con `ModeSwitcher`, `ClickableHexMap` (108 hex), toolbar uguale e opzioni fase-specifiche.
5. Implementare M4+M5 (13 pt): integrazione AI (`infer_hypothesis_space`, `recommend_moves`) + test in [tests/test_spa_recognition_api.py](tests/test_spa_recognition_api.py) + update [README.md](README.md).

### Further Considerations
1. Proposta punti complessivi: 44 pt (M1 5, M2 13, M3 13, M4 8, M5 5), da rifinire dopo la specifica.
2. `warnings` V1 consigliati: `code`, `message`, `scope`, `severity`, senza bloccare le transizioni di fase.
3. Questa è la bozza finale del piano: al prossimo step posso trasformarla in task atomici (checklist per PR) con Definition of Done per ciascun task.

