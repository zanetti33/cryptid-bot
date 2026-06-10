## Piano: Backlog operativo `spa_recognition`

Backlog operativo a milestone con stime a punti relativi, focalizzato su MVP logic-first.

> **Stato complessivo**: **✅ V1 base completato** — backend/API, AI integration e frontend minimale sono presenti e coperti da test.
>
> **Nuovo follow-up richiesto**: **🚧 V1.1 pianificato** — composizione iniziale board tramite `module_templates` + `board_slots`, e colorazione degli esagoni in base al terreno.
>
> **Nuovo follow-up aggiuntivo**: **📝 V1.2 da pianificare** — overlay ricchi di board (animali, strutture, token) e preset di layout (`load default layout`, `reset layout`, `save layout`).

## Gap UX emersi da colmare nel prossimo step

1. **Ordine operativo non corretto**: oggi la UI mostra subito la griglia cliccabile, ma nel flusso reale la prima operazione deve essere la composizione della board assegnando i `module_templates` ai `board_slots`.
2. **Mappa poco leggibile**: gli esagoni non mostrano il colore del proprio territorio (`forest`, `mountain`, `water`, `desert`, `swamp`), quindi la board non è interpretabile a colpo d'occhio.
3. **Mancanza di affordance per il setup**: l'utente non capisce come costruire la board iniziale né quando la composizione è completa.
4. **Overlay informativi incompleti**: la mappa non mostra ancora in modo esplicito animali, strutture o token round/cube direttamente sugli hex.
5. **Mancanza di preset di layout**: non c'è ancora una UX esplicita per caricare il layout canonico, azzerare la composizione corrente o salvare un layout riutilizzabile.

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

### M6 – Board composition UX + terrain-colored hex map (13 pt) 🚧 TODO

| # | Task | Stato |
|---|------|-------|
| M6-1 | Introdurre una nuova fase iniziale `board_layout` prima di `map`, in cui l'utente compone la board scegliendo per ciascuno dei 6 `board_slots` un `section_id` (`A`-`F`) e un'`orientation` (`normal` / `flipped`) | ⏳ Todo |
| M6-2 | Estendere il modello di sessione backend con uno stato dedicato alla composizione board (`placements`, eventuale `structure_markers`, stato di completezza) | ⏳ Todo |
| M6-3 | Aggiungere un endpoint dedicato, preferibilmente `POST /board-layout`, che accetti i placement dei moduli, validi duplicati/mancanze e restituisca la board composta serializzata con metadati tile (`tile_id`, coordinate, `terrain`, `animal`, `section_id`, `local_id`) | ⏳ Todo |
| M6-4 | Riutilizzare `data/module_templates.json`, `data/board_slots.json` e la logica di composizione in `data/board_loader.py` per evitare duplicazione della semantica di board building | ⏳ Todo |
| M6-5 | Realizzare nel frontend un `BoardComposer` con 6 slot visibili, selezione modulo, toggle orientazione e stato di completezza della configurazione | ⏳ Todo |
| M6-6 | Mostrare la `ClickableHexMap` solo dopo che la board è stata composta, oppure in stato read-only finché la composizione non è completa | ⏳ Todo |
| M6-7 | Colorare ogni esagono in base al proprio `terrain` usando una palette stabile e leggibile (es. forest=verde, mountain=grigio, water=blu, desert=giallo, swamp=viola), mantenendo contrasto sufficiente per selezione e testo | ⏳ Todo |
| M6-8 | Aggiungere legenda visiva dei terreni e stato selected/hover che non perda la leggibilità del colore base del territorio | ⏳ Todo |
| M6-9 | Aggiungere warning dedicati (`BOARD_LAYOUT_INCOMPLETE`, `BOARD_LAYOUT_DUPLICATE_SECTION`, `BOARD_LAYOUT_DUPLICATE_SLOT`, `BOARD_LAYOUT_UNKNOWN_SECTION`, `BOARD_LAYOUT_UNKNOWN_ORIENTATION`) non bloccanti ma espliciti | ⏳ Todo |
| M6-10 | Estendere i test backend e frontend: contract tests sull'endpoint di board composition, test adapter board->UI payload, smoke test del flusso `setup -> board_layout -> map -> structures/clues` | ⏳ Todo |

**Gate di uscita**: l'utente riesce prima a comporre la board, poi a vedere una mappa 108 hex colorata e comprensibile, e solo dopo a modificare celle/strutture/clue.

---

### M7 – Rich board overlays + layout presets (18 pt) 📝 PLANNED

| # | Task | Stato |
|---|------|-------|
| M7-1 | Estendere la serializzazione board/tile backend per includere overlay leggibili in UI: `animal`, `structure_type`, `structure_color`, `round_tokens`, `cube_tokens`, `round_token_count`, `cube_token_count` | ⏳ Todo |
| M7-2 | Verificare e consolidare il round-trip tile serialization/deserialization per non perdere animali, strutture o token quando la board viene ricalcolata o aggiornata | ⏳ Todo |
| M7-3 | Mostrare direttamente nella `ClickableHexMap` un layer visivo per gli animali (es. icone/simboli per `bear` e `cougar`) con legenda dedicata | ⏳ Todo |
| M7-4 | Mostrare direttamente nella `ClickableHexMap` un layer visivo per le strutture con codifica di tipo e colore (`standing_stone`, `abandoned_shack`; `white`, `green`, `blue`) | ⏳ Todo |
| M7-5 | Rendere visibili i token `round` e `cube` sugli hex, almeno come badge/contatori; opzionalmente esporre tooltip o dettaglio player-by-player | ⏳ Todo |
| M7-6 | Aggiungere toggle di visibilità in toolbar o pannello mappa: `show animals`, `show structures`, `show tokens`, per ridurre rumore visivo | ⏳ Todo |
| M7-7 | Introdurre il preset action `Load default layout`, che carica il layout canonico definito in `data/game_layout_instance.json` | ⏳ Todo |
| M7-8 | Introdurre l'action `Reset layout`, definita in V1.2 come reset del draft del compositore a 6 slot vuoti/non assegnati, con conferma utente per evitare perdita accidentale | ⏳ Todo |
| M7-9 | Introdurre l'action `Save layout`, con persistenza iniziale semplice (file JSON locale o store in-memory per sessione, da decidere in implementazione), nome preset e validazione duplicati | ⏳ Todo |
| M7-10 | Aggiungere un catalogo preset backend (`list`, `load`, `save`) e relativo adapter dati, senza duplicare la logica di composizione board esistente | ⏳ Todo |
| M7-11 | Migliorare la UX del `BoardComposer` con stato del preset attivo, feedback di salvataggio/reset/load, e distinzione tra `draft layout` e `applied layout` | ⏳ Todo |
| M7-12 | Aggiungere test backend e smoke test frontend per overlay e preset: serializzazione token/animali/strutture, load default, reset, save, reload layout | ⏳ Todo |

**Gate di uscita**: la board mostra in modo leggibile territorio + animali + strutture + token, e il compositore supporta caricamento preset di default, reset del draft e salvataggio di layout riutilizzabili.

---

## Riepilogo punti

| Milestone | Punti | Stato |
|-----------|-------|-------|
| M1 – Specifica | 5 | ✅ Done |
| M2 – Backend | 13 | ✅ Done |
| M3 – Frontend React | 13 | ✅ Done |
| M4 – AI Integration | 8 | ✅ Done |
| M5 – Test + Docs | 5 | ✅ Done |
| M6 – Board composition + terrain map | 13 | 🚧 Todo |
| M7 – Overlays + layout presets | 18 | 📝 Planned |
| **Totale roadmap aggiornata** | **75** | **🚧 In corso (follow-up V1.1 + V1.2)** |

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
