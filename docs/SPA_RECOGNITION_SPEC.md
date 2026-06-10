# SPA Recognition - Specifica tecnica (M1 + follow-up M6)

## 1) Obiettivo

Definire una specifica operativa per il modulo `spa_recognition` con approccio MVP logic-first:
- stato partita/sessione in memoria,
- composizione iniziale della board assegnando `module_templates` ai `board_slots`,
- mappa da 108 esagoni cliccabile,
- esagoni colorati in base al territorio per rendere leggibile la board,
- overlay visivi per animali, strutture e token round/cube,
- preset per caricare, resettare e salvare layout di board,
- UX coerente in due modalita (`Structures`, `Clues`),
- warning non bloccanti,
- ricalcolo AI esplicito via bottone,
- compatibilita con `GameSnapshot` e con i moduli gia presenti (`game_model`, `ai`, `recognition`).

Questa specifica copre il backlog M1..M7 e fornisce i contratti V1/V1.1/V1.2 per backend e frontend.

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
  - step iniziale di composizione board (6 slot × modulo + orientazione),
  - switch modalita (`Structures` / `Clues`),
  - mappa 108 hex cliccabile,
  - esagoni colorati per territorio,
  - overlay opzionali per animali, strutture e token,
  - preset di layout (`load default`, `reset`, `save`),
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
- `BOARD_LAYOUT_INCOMPLETE`
- `BOARD_LAYOUT_DUPLICATE_SECTION`
- `BOARD_LAYOUT_DUPLICATE_SLOT`
- `BOARD_LAYOUT_PRESET_NOT_FOUND`
- `BOARD_LAYOUT_PRESET_DUPLICATE_NAME`
- `BOARD_LAYOUT_SAVE_INVALID`
- `STRUCTURE_COLOR_DUPLICATE`
- `CLUE_SET_INCOMPLETE`
- `TOKEN_PATTERN_SUSPICIOUS`
- `AI_INPUT_PARTIAL`

## 6) Contratti API V1 (backend)

Tutti gli endpoint V1/V1.1 sono `POST` e operano su una sessione in memoria.

### `POST /setup`
Inizializza o aggiorna metadati sessione.
- Input: player ids, ordine turno, bot player id, opzioni V1.
- Output: session snapshot + warning.

### `POST /board-layout`
Compone la board iniziale assegnando i `module_templates` ai `board_slots`.
- Input: elenco placements `{slot_id, section_id, orientation}`.
- Validazioni principali: slot duplicati, section duplicate, orientation invalida, composizione incompleta.
- Output: stato board layout + board serializzata pronta per la UI, con tile metadata (`tile_id`, coordinate, `terrain`, `animal`, `section_id`, `local_id`).

### `POST /board-layout/load-default`
Carica nel draft/sessione il layout canonico definito dal progetto.
- Input: session id.
- Output: placements del layout di default + board serializzata aggiornata.

### `POST /board-layout/reset`
Resetta il draft del compositore board.
- Input: session id.
- Output: stato board layout vuoto/non completo, senza placements attivi.

### `POST /board-layout/save`
Salva il layout corrente come preset riutilizzabile.
- Input: session id, `preset_name`, placements correnti o layout applicato.
- Output: catalogo preset aggiornato + conferma salvataggio.

### `POST /board-layout/load`
Carica un preset salvato dall'utente.
- Input: session id, `preset_name`.
- Output: placements del preset + board serializzata aggiornata.

### `POST /map`
Registra o aggiorna stato mappa utile alla vista cliccabile dopo la composizione board.
- Input: eventuali token osservati e overlay utente sulla board gia composta.
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
- `phase` (setup/board_layout/map/structures/clues/review)
- `setup` (players, turn order, bot)
- `board_layout_state` (placements per slot, completezza, board serializzata, preset attivo, draft/applicato)
- `map_state` (token placements osservati + riferimenti alla board composta)
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
- uso della board composta a partire da `data/module_templates.json` + `data/board_slots.json` + placements scelti in UI.
- nessuna duplicazione della semantica token/clue gia in `game_model`.

Serializzazione tile raccomandata V1.2:
- `tile_id`, `q`, `r`, `terrain`
- `animal`
- `structure_type`, `structure_color`
- `round_tokens`, `cube_tokens`
- `round_token_count`, `cube_token_count`
- `section_id`, `local_id`

Integrazione:
- `ai.inference.infer_hypothesis_space(snapshot)`
- `ai.strategy.recommend_moves(snapshot, hypothesis_space=..., top_k=...)`

Output AI nel backend:
- vista raw (strutture dati originali),
- vista serializzata frontend-friendly.

## 9) Flusso UX corretto della SPA

Ordine operativo desiderato:

1. **Setup sessione**: configurazione player ids, turn order, bot player id.
2. **Board composition**: l'utente assegna i 6 moduli (`A`-`F`) ai 6 `board_slots`, scegliendo anche l'orientazione (`normal` / `flipped`).
3. **Map review/edit**: solo dopo la composizione completa si mostra la mappa 108 hex cliccabile, con ogni cella colorata in base al proprio territorio.
4. **Structures mode**: inserimento/aggiornamento strutture.
5. **Clues mode**: inserimento note/clue/constraint.
6. **Review + AI**: ricalcolo AI esplicito via bottone.

Regola UX chiave V1.1:
- la griglia degli hex non deve essere il primo elemento modificabile;
- la prima affordance della UI deve essere il compositore della board;
- la mappa deve diventare realmente leggibile anche senza testo numerico, grazie ai colori dei territori.

Regola UX chiave V1.2:
- gli overlay di animali, strutture e token devono essere leggibili ma disattivabili;
- il compositore deve distinguere tra `draft layout` e `layout applicato`;
- le action `load default layout`, `reset layout`, `save layout` devono avere semantica chiara e feedback esplicito.

Palette terreno consigliata V1.1:
- `forest` → verde
- `mountain` → grigio
- `water` → blu
- `desert` → giallo/sabbia
- `swamp` → viola

Overlay consigliati V1.2:
- `bear` / `cougar` con icone o glifi dedicati
- strutture con icona per tipo + accent color per `structure_color`
- token `round` e `cube` come badge/stack/contatori in overlay sull'hex

## 10) Milestone e stime (punti relativi)

Totale roadmap aggiornata: **75 pt**

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
- flusso utente base completo setup->map->structures/clues con stato consistente, da riallineare in M6 al nuovo ordine `setup -> board_layout -> map`.

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

### M6 - Board composition UX + terrain-colored hex map (13 pt)
Deliverable:
- estensione backend con `board_layout_state`
- endpoint `POST /board-layout`
- componente frontend dedicato alla composizione board
- mappa hex colorata in base al `terrain`

Dipendenze:
- M2 e M3 completati.

Gate uscita:
- l'utente compone prima la board e vede poi una mappa colorata, coerente con il layout scelto.

### M7 - Rich board overlays + layout presets (18 pt)
Deliverable:
- serializzazione tile estesa con overlay animali/strutture/token
- mappa con layer opzionali per animali, strutture e token
- preset actions `load default layout`, `reset layout`, `save layout`, `load layout`
- catalogo preset backend e feedback UI dedicato

Dipendenze:
- M6 completato.

Gate uscita:
- la board e leggibile sia come territorio sia come overlay informativo, e il compositore supporta flussi rapidi di caricamento/reset/salvataggio layout.

## 11) Criteri di accettazione M1/M6

M1 e accettato se:
1. La spec descrive chiaramente obiettivo, scope/non-scope e principi V1.
2. Sono definiti gli endpoint previsti e il loro ruolo.
3. E definito il modello warning (`code`, `message`, `scope`, `severity`) non bloccante.
4. E documentata la compatibilita con `GameSnapshot` e le funzioni AI esistenti.
5. Sono presenti milestone M1..M6 con punti, dipendenze e gate.
6. Sono elencati rischi principali con mitigazioni e piano test alto livello.

M6 e accettato se:
1. La UI parte dalla composizione board e non dalla modifica diretta delle celle.
2. Ogni esagono mostra il colore del proprio territorio in modo leggibile.
3. La composizione dei 6 slot impedisce ambiguita evidenti tramite warning chiari.
4. La board composta viene serializzata in modo coerente con `GameSnapshot`.

M7 e accettato se:
1. Animali, strutture e token sono visibili direttamente sulla mappa senza sacrificare la leggibilita del territorio.
2. Gli overlay possono essere attivati/disattivati dall'utente.
3. `Load default layout`, `reset layout` e `save layout` hanno comportamento esplicito e testato.
4. I preset salvati possono essere ricaricati nella stessa UX senza ricomporre manualmente i 6 slot.

## 12) Definition of Done (DoD) M1/M6

- Documento creato in `docs/SPA_RECOGNITION_SPEC.md`.
- Revisione lessicale/tecnica completata.
- Nessuna ambiguita critica su confini V1 e contratti API.
- Backlog implementativo direttamente derivabile dal documento.

DoD M6:
- esiste un flusso `setup -> board_layout -> map`
- la board composition usa i dati reali di `module_templates` e `board_slots`
- la mappa mostra i colori dei territori e rimane selezionabile/modificabile
- sono presenti test backend e smoke test frontend del nuovo flow

DoD M7:
- la serializzazione tile include animali, strutture e token in forma UI-friendly
- la mappa supporta overlay multipli leggibili e toggle di visibilita
- esistono action di preset almeno per default/reset/save/load
- backend e frontend hanno test dedicati per i flussi preset e per gli overlay principali

## 13) Rischi e mitigazioni

1. **Ambiguita regole Cryptid in input incompleto**
   - Mitigazione: warning espliciti + fallback permissivi.
2. **Deriva tra modello sessione e `GameSnapshot`**
   - Mitigazione: adapter unico e test di mapping dedicati.
3. **UI non allineata al backend state machine**
   - Mitigazione: phase model condiviso e contract tests.
4. **Qualita suggerimenti AI con dati parziali**
   - Mitigazione: warnings `AI_INPUT_PARTIAL` + rationale in output.
5. **Board composition confusa o troppo tecnica per l'utente**
   - Mitigazione: UI a slot espliciti, preview immediata, warning di composizione incompleta/duplicata.
6. **Colori terreno poco leggibili con selected/hover**
   - Mitigazione: palette accessibile + overlay di selezione separato dal fill base.
7. **Overlay troppo densi e rumorosi**
   - Mitigazione: toggle di visibilita, legenda, layering e gerarchia visiva chiara.
8. **Semantica ambigua tra reset, load default e save**
   - Mitigazione: definizioni esplicite nel prodotto e feedback visuale su draft vs applied layout.
9. **Persistenza preset non stabile o non portabile**
   - Mitigazione: iniziare con JSON semplice o store locale controllato, con adapter separato dal dominio.

## 14) Piano test ad alto livello

- **Unit test backend models/store**: creazione, update, merge warning, reset.
- **Board composition tests**: placements validi, duplicati, incompleti, orientazioni invalide.
- **Preset tests**: load default, reset, save, duplicate preset name, load preset inesistente.
- **API test**: happy path + payload incompleti (attesi warning, non blocco).
- **Adapter test**: session state -> `GameSnapshot` coerente.
- **AI integration test**: `/recalculate` produce payload serializzabile e stabile.
- **Overlay tests**: tile serialization di animali, strutture, round/cube tokens e relativo rendering.
- **Frontend smoke test**: setup board, preview mappa colorata, toggle overlay, load/reset/save layout, cambio modalita, click map, call API, refresh suggerimenti.

## 15) Sequenza operativa consigliata dopo M1

1. Implementare M2 con contratti minimi e validazione payload.
2. Agganciare M3 con stub API gia stabili.
3. Attivare M4 solo dopo stabilizzazione session model.
4. Chiudere con M5 test/documentazione e checklist di rilascio MVP.
5. Introdurre M6 per riallineare la UX al flusso reale del gioco: composizione board prima, modifica celle dopo.
6. Introdurre M7 per rendere la board autoesplicativa (overlay) e il compositore veloce da riusare (preset).

