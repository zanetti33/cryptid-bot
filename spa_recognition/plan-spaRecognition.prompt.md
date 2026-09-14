## Piano: Backlog operativo `spa_recognition`

Backlog operativo a milestone con stime a punti relativi, focalizzato su MVP logic-first.

> **Stato complessivo**: **✅ V1 base completato** — backend/API, AI integration e frontend minimale sono presenti e coperti da test.
>
> **V1.1**: **✅ Completato** — composizione iniziale board tramite `module_templates` + `board_slots` (endpoint `/board-layout`), colorazione degli esagoni in base al terreno con legenda, e warning dedicati. Vedi M6 sotto.
>
> **V1.2**: **🚧 Parzialmente completato** — overlay ricchi di board (animali, strutture, token) e i relativi toggle di visibilità sono implementati; i preset di layout (`load default layout` reale via catalogo, `reset layout`, `save layout`) restano da implementare. Vedi M7 sotto.

## Gap UX residui

1. ~~Ordine operativo non corretto~~ - **Risolto**: la UI ora richiede la composizione board (`BoardComposer`) prima di mostrare la griglia cliccabile.
2. ~~Mappa poco leggibile~~ - **Risolto**: `ClickableHexMap` colora ogni esagono in base al territorio (`TERRAIN_COLORS`) con contrasto testo/hover gestito.
3. ~~Mancanza di affordance per il setup~~ - **Risolto**: `BoardComposer` mostra stato di completezza e sblocca la mappa solo a composizione valida.
4. ~~Overlay informativi incompleti~~ - **Risolto**: animali, strutture e badge round/cube sono renderizzati sugli hex con toggle `show animals` / `show structures` / `show tokens` in toolbar.
5. **Ancora aperto**: non esiste un catalogo preset backend (`list`/`load`/`save`) né azioni esplicite `Reset layout` / `Save layout` nel `BoardComposer`. Il "load default" attuale in frontend usa uno scenario hardcoded (`defaultLayoutScenario.js`), non il preset `default_layout` esposto da `/catalog`.

---

## Milestone e Task

### M1 – Specifica completa (5 pt) ✅ DONE

| # | Task | Stato |
|---|------|-------|
| M1-1 | Redigere specifica in `docs/SPA_RECOGNITION_SPEC.md` con scope, contratti, warnings, milestone, rischi | ✅ Done |
| M1-2 | Definire modello warning V1 (`code`, `message`, `scope`, `severity`) non bloccante | ✅ Done |
| M1-3 | Documentare compatibilità con `GameSnapshot` e AI esistente | ✅ Done |
| M1-4 | Elencare milestone M1..M6 con punti, dipendenze e gate di uscita | ✅ Done |

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

### M6 – Board composition UX + terrain-colored hex map (13 pt) ✅ DONE

| # | Task | Stato |
|---|------|-------|
| M6-1 | Introdurre una nuova fase iniziale `board_layout` prima di `map`, in cui l'utente compone la board scegliendo per ciascuno dei 6 `board_slots` un `section_id` (`A`-`F`) e un'`orientation` (`normal` / `flipped`) | ✅ Done (`SessionPhase` in `backend/models.py`) |
| M6-2 | Estendere il modello di sessione backend con uno stato dedicato alla composizione board (`placements`, eventuale `structure_markers`, stato di completezza) | ✅ Done (`BoardLayoutState` in `backend/models.py`) |
| M6-3 | Aggiungere un endpoint dedicato, preferibilmente `POST /board-layout`, che accetti i placement dei moduli, validi duplicati/mancanze e restituisca la board composta serializzata con metadati tile (`tile_id`, coordinate, `terrain`, `animal`, `section_id`, `local_id`) | ✅ Done (`post_board_layout` in `backend/api.py`) |
| M6-4 | Riutilizzare `data/module_templates.json`, `data/board_slots.json` e la logica di composizione in `data/board_loader.py` per evitare duplicazione della semantica di board building | ✅ Done |
| M6-5 | Realizzare nel frontend un `BoardComposer` con 6 slot visibili, selezione modulo, toggle orientazione e stato di completezza della configurazione | ✅ Done (`frontend/src/components/BoardComposer.jsx`) |
| M6-6 | Mostrare la `ClickableHexMap` solo dopo che la board è stata composta, oppure in stato read-only finché la composizione non è completa | ✅ Done |
| M6-7 | Colorare ogni esagono in base al proprio `terrain` usando una palette stabile e leggibile (es. forest=verde, mountain=grigio, water=blu, desert=giallo, swamp=viola), mantenendo contrasto sufficiente per selezione e testo | ✅ Done (`TERRAIN_COLORS` + `getContrastColor` in `ClickableHexMap.jsx`) |
| M6-8 | Aggiungere legenda visiva dei terreni e stato selected/hover che non perda la leggibilità del colore base del territorio | ✅ Done |
| M6-9 | Aggiungere warning dedicati (`BOARD_LAYOUT_INCOMPLETE`, `BOARD_LAYOUT_DUPLICATE_SECTION`, `BOARD_LAYOUT_DUPLICATE_SLOT`, `BOARD_LAYOUT_UNKNOWN_SECTION`, `BOARD_LAYOUT_UNKNOWN_ORIENTATION`) non bloccanti ma espliciti | ✅ Done (`backend/api.py`) |
| M6-10 | Estendere i test backend e frontend: contract tests sull'endpoint di board composition, test adapter board->UI payload, smoke test del flusso `setup -> board_layout -> map -> structures/clues` | ✅ Done (`tests/test_spa_recognition_api.py`) |

**Gate di uscita**: l'utente riesce prima a comporre la board, poi a vedere una mappa 108 hex colorata e comprensibile, e solo dopo a modificare celle/strutture/clue. → ✅

---

### M7 – Rich board overlays + layout presets (18 pt) 🚧 PARTIALLY DONE

| # | Task | Stato |
|---|------|-------|
| M7-1 | Estendere la serializzazione board/tile backend per includere overlay leggibili in UI: `animal`, `structure_type`, `structure_color`, `round_tokens`, `cube_tokens`, `round_token_count`, `cube_token_count` | ✅ Done |
| M7-2 | Verificare e consolidare il round-trip tile serialization/deserialization per non perdere animali, strutture o token quando la board viene ricalcolata o aggiornata | ✅ Done |
| M7-3 | Mostrare direttamente nella `ClickableHexMap` un layer visivo per gli animali (es. icone/simboli per `bear` e `cougar`) con legenda dedicata | ✅ Done (bordi colorati per animale, `ClickableHexMap.jsx`) |
| M7-4 | Mostrare direttamente nella `ClickableHexMap` un layer visivo per le strutture con codifica di tipo e colore (`standing_stone`, `abandoned_shack`; `white`, `green`, `blue`) | ✅ Done |
| M7-5 | Rendere visibili i token `round` e `cube` sugli hex, almeno come badge/contatori; opzionalmente esporre tooltip o dettaglio player-by-player | ✅ Done (badge per giocatore) |
| M7-6 | Aggiungere toggle di visibilità in toolbar o pannello mappa: `show animals`, `show structures`, `show tokens`, per ridurre rumore visivo | ✅ Done (`Toolbar.jsx`) |
| M7-7 | Introdurre il preset action `Load default layout`, che carica il layout canonico definito in `data/game_layout_instance.json` | 🚧 Parziale — il frontend applica uno scenario di default hardcoded (`defaultLayoutScenario.js`) invece di caricare il preset `default_layout` dal catalogo `/catalog` |
| M7-8 | Introdurre l'action `Reset layout`, definita in V1.2 come reset del draft del compositore a 6 slot vuoti/non assegnati, con conferma utente per evitare perdita accidentale | ⏳ Todo — nessuna azione "Reset layout" trovata nel `BoardComposer` |
| M7-9 | Introdurre l'action `Save layout`, con persistenza iniziale semplice (file JSON locale o store in-memory per sessione, da decidere in implementazione), nome preset e validazione duplicati | ⏳ Todo |
| M7-10 | Aggiungere un catalogo preset backend (`list`, `load`, `save`) e relativo adapter dati, senza duplicare la logica di composizione board esistente | ⏳ Todo — `/catalog` oggi espone solo il layout `default_layout` in sola lettura, nessun `save`/`list` di preset utente |
| M7-11 | Migliorare la UX del `BoardComposer` con stato del preset attivo, feedback di salvataggio/reset/load, e distinzione tra `draft layout` e `applied layout` | ⏳ Todo |
| M7-12 | Aggiungere test backend e smoke test frontend per overlay e preset: serializzazione token/animali/strutture, load default, reset, save, reload layout | 🚧 Parziale — overlay coperti da test, i flussi preset (save/reset/load) no |

**Gate di uscita**: la board mostra in modo leggibile territorio + animali + strutture + token (✅), e il compositore supporta caricamento preset di default, reset del draft e salvataggio di layout riutilizzabili (⏳ ancora da fare: M7-8, M7-9, M7-10, M7-11).

---

## Riepilogo punti

| Milestone | Punti | Stato |
|-----------|-------|-------|
| M1 – Specifica | 5 | ✅ Done |
| M2 – Backend | 13 | ✅ Done |
| M3 – Frontend React | 13 | ✅ Done |
| M4 – AI Integration | 8 | ✅ Done |
| M5 – Test + Docs | 5 | ✅ Done |
| M6 – Board composition + terrain map | 13 | ✅ Done |
| M7 – Overlays + layout presets | 18 | 🚧 Parziale (overlay ✅, preset save/reset/list ⏳) |
| **Totale roadmap aggiornata** | **75** | **🚧 In corso (V1.1 completo, V1.2 parziale — mancano i preset di layout)** |

---

## Note finali (V1)

- **Warnings non bloccanti**: tutti i warning usano `code`, `message`, `scope`, `severity` e non interrompono il flusso.
- **Compatibilità**: il modulo non duplica logica di `game_model`; usa l'adapter `_build_snapshot_from_session` per convertire stato sessione → `GameSnapshot`.
- **Out of scope V1**: persistenza DB, multi-sessione distribuita, auth, undo/redo completo.
- **Frontend**: richiede `npm install` + `npm run dev` nella cartella `spa_recognition/frontend/`. Il plugin `@vitejs/plugin-react` è necessario per il supporto JSX.
- **Priorità UX aggiornata**: il prossimo incremento deve partire dalla composizione board (`module_templates` → `board_slots`) e solo dopo rendere disponibile la mappa cliccabile colorata per territorio.
- **Semantica preset proposta V1.2**:
  - `Load default layout` = carica il layout canonico da `data/game_layout_instance.json`
  - `Reset layout` = azzera il draft corrente del compositore a slot vuoti
  - `Save layout` = salva il draft/applicato corrente come preset nominato riutilizzabile
