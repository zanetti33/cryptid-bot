## Piano: Backlog operativo `spa_recognition`

Backlog operativo a milestone con stime a punti relativi, focalizzato su MVP logica-first.

> **Stato complessivo**: **✅ Completato** — tutti i test passano (67 test, 0 fallimenti).

---

## Milestone e Task

### M1 – Specifica completa (5 pt) ✅ DONE

| # | Task | Stato |
|---|------|-------|
| M1-1 | Redigere specifica in `docs/SPA_RECOGNITION_SPEC.md` con scope, contratti, warnings, milestone, rischi | ✅ Done |
| M1-2 | Definire modello warning V1 (`code`, `message`, `scope`, `severity`) non bloccante | ✅ Done |
| M1-3 | Documentare compatibilità con `GameSnapshot` e AI esistente | ✅ Done |
| M1-4 | Elencare milestone M1..M5 con punti, dipendenze e gate di uscita | ✅ Done |

**Deliverable**: [`docs/SPA_RECOGNITION_SPEC.md`](../docs/SPA_RECOGNITION_SPEC.md)

---

### M2 – Backend contract + session store (13 pt) ✅ DONE

| # | Task | Stato |
|---|------|-------|
| M2-1 | `spa_recognition/__init__.py` — export pubblico del modulo | ✅ Done |
| M2-2 | `spa_recognition/backend/models.py` — dataclass `WarningItem`, `SetupState`, `MapState`, `StructuresState`, `CluesState`, `AiState`, `SessionState`, `ApiResult`, `merge_warnings` | ✅ Done |
| M2-3 | `spa_recognition/backend/session_store.py` — `SessionStore` thread-safe in-memory | ✅ Done |
| M2-4 | `spa_recognition/backend/api.py` — `SpaRecognitionApi` con endpoint `POST /setup /map /structures /clues /recalculate` | ✅ Done |
| M2-5 | `spa_recognition/backend/http_server.py` — server HTTP standalone con CORS | ✅ Done |
| M2-6 | `spa_recognition/backend/demo_runner.py` — demo CLI del workflow completo | ✅ Done |

**Gate di uscita**: endpoint rispondono con stato e warning coerenti → ✅

---

### M3 – Frontend React minimale (13 pt) ✅ DONE

| # | Task | Stato |
|---|------|-------|
| M3-1 | `spa_recognition/frontend/src/main.jsx` — entry point React | ✅ Done |
| M3-2 | `spa_recognition/frontend/src/App.jsx` — shell applicazione con state management | ✅ Done |
| M3-3 | `spa_recognition/frontend/src/components/ModeSwitcher.jsx` — switch `Structures` / `Clues` | ✅ Done |
| M3-4 | `spa_recognition/frontend/src/components/ClickableHexMap.jsx` — griglia 108 hex cliccabile | ✅ Done |
| M3-5 | `spa_recognition/frontend/src/components/Toolbar.jsx` — toolbar con fase e bottone Recalculate AI | ✅ Done |
| M3-6 | `spa_recognition/frontend/src/api/client.js` — fetch helper verso backend | ✅ Done |
| M3-7 | `spa_recognition/frontend/src/styles.css` — stili base responsive | ✅ Done |
| M3-8 | `spa_recognition/frontend/package.json` — dipendenze React + Vite + `@vitejs/plugin-react` | ✅ Done |
| M3-9 | `spa_recognition/frontend/vite.config.js` — config Vite con plugin React per supporto JSX | ✅ Done |
| M3-10 | `spa_recognition/frontend/index.html` — HTML entry point | ✅ Done |

**Gate di uscita**: flusso utente setup→map→structures/clues con stato consistente → ✅

---

### M4 – Integrazione AI (8 pt) ✅ DONE

| # | Task | Stato |
|---|------|-------|
| M4-1 | Wiring `/recalculate` → `infer_hypothesis_space(snapshot)` | ✅ Done |
| M4-2 | Wiring `/recalculate` → `recommend_moves(snapshot, hypothesis_space, top_k)` | ✅ Done |
| M4-3 | Serializzazione `HypothesisSpace` in JSON frontend-friendly | ✅ Done |
| M4-4 | Serializzazione `RecommendedMove` in JSON frontend-friendly | ✅ Done |
| M4-5 | Visualizzazione `ui_payload` con `global_candidate_tiles`, `global_guaranteed_tiles`, `top_move` | ✅ Done |
| M4-6 | Gestione errori AI graceful con warning `AI_RECALCULATE_FAILED` (non bloccante) | ✅ Done |

**Gate di uscita**: suggerimenti AI serializzabili e aggiornati su bottone → ✅

---

### M5 – Test + documentazione (5 pt) ✅ DONE

| # | Task | Stato |
|---|------|-------|
| M5-1 | `tests/test_spa_recognition_api.py` — 4 test API integration (setup/map, payload permissivo, structures/clues, recalculate) | ✅ Done |
| M5-2 | `tests/test_spa_models_and_store.py` — 20 unit test (WarningItem, merge_warnings, SessionState, SessionStore, adapter snapshot) | ✅ Done |
| M5-3 | `README.md` — sezione `spa_recognition` con architettura, endpoint, comandi Docker | ✅ Done |
| M5-4 | `docs/SPA_RECOGNITION_SPEC.md` — piano test ad alto livello, criteri accettazione, DoD | ✅ Done |

**Gate di uscita**: test verdi in CI locale, docs minime operative → ✅ (67/67 test)

---

## Riepilogo punti

| Milestone | Punti | Stato |
|-----------|-------|-------|
| M1 – Specifica | 5 | ✅ Done |
| M2 – Backend | 13 | ✅ Done |
| M3 – Frontend React | 13 | ✅ Done |
| M4 – AI Integration | 8 | ✅ Done |
| M5 – Test + Docs | 5 | ✅ Done |
| **Totale** | **44** | **✅ Completato** |

---

## Note finali (V1)

- **Warnings non bloccanti**: tutti i warning usano `code`, `message`, `scope`, `severity` e non interrompono il flusso.
- **Compatibilità**: il modulo non duplica logica di `game_model`; usa l'adapter `_build_snapshot_from_session` per convertire stato sessione → `GameSnapshot`.
- **Out of scope V1**: persistenza DB, multi-sessione distribuita, auth, undo/redo completo.
- **Frontend**: richiede `npm install` + `npm run dev` nella cartella `spa_recognition/frontend/`. Il plugin `@vitejs/plugin-react` è necessario per il supporto JSX.
