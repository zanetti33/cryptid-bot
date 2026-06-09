# SPA Recognition - Specifica tecnica (M1)

## 1) Obiettivo

Definire una specifica operativa per il modulo `spa_recognition` con approccio MVP logic-first:
- stato partita/sessione in memoria,
- mappa da 108 esagoni cliccabile,
- UX coerente in due modalita (`Structures`, `Clues`),
- warning non bloccanti,
- ricalcolo AI esplicito via bottone,
- compatibilita con `GameSnapshot` e con i moduli gia presenti (`game_model`, `ai`, `recognition`).

Questa specifica copre il backlog M1..M5 e fornisce i contratti V1 per backend e frontend.

## 2) Contesto architetturale corrente

Il progetto e gia separato in moduli:
- `game_model/`: logica gioco e modello (`GameSnapshot`, board, clue),
- `ai/`: inferenza (`infer_hypothesis_space`) e strategia (`recommend_moves`),
- `recognition/`: estrazione stato board da immagini,
- `discord_bot/`: integrazione futura.

`spa_recognition` si inserisce come layer applicativo per input manuale/assistito e orchestrazione AI, senza duplicare la logica del dominio.

## 3) Scope MVP (V1)

### In scope
- Sessione in memoria per setup e progressione fase.
- API backend permissive (validano ma non bloccano salvo errori strutturali gravi).
- Frontend React minimale con:
  - switch modalita (`Structures` / `Clues`),
  - mappa 108 hex cliccabile,
  - toolbar coerente tra fasi,
  - bottone `Recalculate AI`.
- Integrazione AI per calcolo hypothesis space e mosse suggerite.
- Test API principali e smoke test del flusso.

### Out of scope (V1)
- Persistenza su DB.
- Multi-sessione distribuita o sincronizzazione realtime multi-client.
- Hard validation di tutte le regole del regolamento (solo warning non bloccanti in V1).
- UX avanzata (undo/redo completo, collaboration live, auth).

## 4) Principi V1

1. **Logic-first**: prima correttezza del dato e del flusso, poi raffinamento UX.
2. **Permissivo ma trasparente**: quasi tutte le incoerenze diventano warning, non stop.
3. **Single source of truth**: stato centralizzato di sessione backend.
4. **Compatibilita stretta**: adapter verso `GameSnapshot` per evitare fork del modello.
5. **Modularita**: API, stato, mapping e AI integration separati.

## 5) Modello warning non bloccante

Schema warning V1:

```json
{
  "code": "string_machine_readable",
  "message": "string_human_readable",
  "scope": "setup|map|structures|clues|recalculate|session",
  "severity": "info|warn|error"
}
```

Regole:
- `severity=error` in V1 resta non bloccante, salvo errori di parsing/shape payload.
- Le API rispondono con stato aggiornato + lista warning corrente.
- I warning devono essere stabili e deduplicabili (stesso `code` + `scope` + target).

Esempi warning iniziali:
- `TURN_ORDER_MISSING_BOT`
- `PLAYER_COUNT_UNUSUAL`
- `STRUCTURE_COLOR_DUPLICATE`
- `CLUE_SET_INCOMPLETE`
- `TOKEN_PATTERN_SUSPICIOUS`
- `AI_INPUT_PARTIAL`

## 6) Contratti API V1 (backend)

Tutti gli endpoint V1 sono `POST` e operano su una sessione in memoria.

### `POST /setup`
Inizializza o aggiorna metadati sessione.
- Input: player ids, ordine turno, bot player id, opzioni V1.
- Output: session snapshot + warning.

### `POST /map`
Registra o aggiorna stato mappa utile alla vista cliccabile.
- Input: board identity/layout + eventuali token osservati.
- Output: stato mappa normalizzato + warning.

### `POST /structures`
Gestisce dati strutture (monolith/shack/tent ecc.) in modalita `Structures`.
- Input: strutture per tile (tipo, colore, presenza).
- Output: stato strutture + warning.

### `POST /clues`
Gestisce dati clue in modalita `Clues`.
- Input: clue note/constraint per player o sessione.
- Output: stato clues + warning.

### `POST /recalculate`
Esegue pipeline AI su stato corrente.
- Input: opzionale (es. `top_k`).
- Output: hypothesis space, mosse consigliate, warning.

## 7) Stato sessione in memoria

Struttura logica prevista (`spa_recognition/backend/models.py`):
- `session_id`
- `phase` (setup/map/structures/clues/review)
- `setup` (players, turn order, bot)
- `map_state` (tile state, token placements osservati)
- `structures_state`
- `clues_state`
- `ai_state` (ultimo risultato inferenza/strategia)
- `warnings` (lista warning correnti)
- `updated_at`

Store in memoria (`spa_recognition/backend/session_store.py`):
- dict keyed by `session_id`,
- operazioni atomiche base: get/create/update/reset,
- strategia TTL opzionale (non bloccante per V1, ma prevista).

## 8) Compatibilita con `GameSnapshot` e AI

Adapter richiesto:
- conversione da stato sessione a `game_model.state.GameSnapshot`.
- nessuna duplicazione della semantica token/clue gia in `game_model`.

Integrazione:
- `ai.inference.infer_hypothesis_space(snapshot)`
- `ai.strategy.recommend_moves(snapshot, hypothesis_space=..., top_k=...)`

Output AI nel backend:
- vista raw (strutture dati originali),
- vista serializzata frontend-friendly.

## 9) Milestone e stime (punti relativi)

Totale: **44 pt**

### M1 - Specifica completa (5 pt)
Deliverable:
- `docs/SPA_RECOGNITION_SPEC.md` con scope, contratti, warning, milestones.

Dipendenze:
- allineamento con architettura esistente (`README.md`, `game_model`, `ai`).

Gate uscita:
- specifica revisionata e approvata, pronta per task implementativi.

### M2 - Backend contract + session store (13 pt)
Deliverable:
- `spa_recognition/__init__.py`
- `spa_recognition/backend/models.py`
- `spa_recognition/backend/session_store.py`
- `spa_recognition/backend/api.py` (endpoint base)

Dipendenze:
- M1 approvato.

Gate uscita:
- endpoint rispondono con stato e warning coerenti.

### M3 - Frontend React minimale (13 pt)
Deliverable:
- `spa_recognition/frontend/src` con `ModeSwitcher`, `ClickableHexMap`, toolbar uniforme.

Dipendenze:
- M2 API disponibili.

Gate uscita:
- flusso utente completo setup->map->structures/clues con stato consistente.

### M4 - Integrazione AI (8 pt)
Deliverable:
- wiring `/recalculate` con inferenza e strategia.

Dipendenze:
- M2 stabile, M3 navigazione pronta.

Gate uscita:
- suggerimenti AI visualizzati e aggiornati su richiesta bottone.

### M5 - Test + documentazione utente/dev (5 pt)
Deliverable:
- `tests/test_spa_recognition_api.py`
- update `README.md` (setup, run, limiti V1)

Dipendenze:
- M2-M4 completati.

Gate uscita:
- test verdi in CI locale, docs minime operative.

## 10) Criteri di accettazione M1

M1 e accettato se:
1. La spec descrive chiaramente obiettivo, scope/non-scope e principi V1.
2. Sono definiti i 5 endpoint previsti e il loro ruolo.
3. E definito il modello warning (`code`, `message`, `scope`, `severity`) non bloccante.
4. E documentata la compatibilita con `GameSnapshot` e le funzioni AI esistenti.
5. Sono presenti milestone M1..M5 con punti, dipendenze e gate.
6. Sono elencati rischi principali con mitigazioni e piano test alto livello.

## 11) Definition of Done (DoD) M1

- Documento creato in `docs/SPA_RECOGNITION_SPEC.md`.
- Revisione lessicale/tecnica completata.
- Nessuna ambiguita critica su confini V1 e contratti API.
- Backlog implementativo direttamente derivabile dal documento.

## 12) Rischi e mitigazioni

1. **Ambiguita regole Cryptid in input incompleto**
   - Mitigazione: warning espliciti + fallback permissivi.
2. **Deriva tra modello sessione e `GameSnapshot`**
   - Mitigazione: adapter unico e test di mapping dedicati.
3. **UI non allineata al backend state machine**
   - Mitigazione: phase model condiviso e contract tests.
4. **Qualita suggerimenti AI con dati parziali**
   - Mitigazione: warnings `AI_INPUT_PARTIAL` + rationale in output.

## 13) Piano test ad alto livello

- **Unit test backend models/store**: creazione, update, merge warning, reset.
- **API test**: happy path + payload incompleti (attesi warning, non blocco).
- **Adapter test**: session state -> `GameSnapshot` coerente.
- **AI integration test**: `/recalculate` produce payload serializzabile e stabile.
- **Frontend smoke test**: cambio modalita, click map, call API, refresh suggerimenti.

## 14) Sequenza operativa consigliata dopo M1

1. Implementare M2 con contratti minimi e validazione payload.
2. Agganciare M3 con stub API gia stabili.
3. Attivare M4 solo dopo stabilizzazione session model.
4. Chiudere con M5 test/documentazione e checklist di rilascio MVP.

