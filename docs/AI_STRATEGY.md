# AI Strategy

## Stato attuale dell'implementazione

Questo documento è nato come **schizzo di design** (pseudocodice) prima dell'implementazione reale ed è
mantenuto per contesto storico sulle idee alla base dell'algoritmo. Il codice effettivo in `ai/` non usa
questi nomi di funzione né la struttura a matrice booleana descritta sotto, ma implementa concetti simili:

| Concetto nello pseudocodice | Implementazione reale |
|---|---|
| Matrice maestra $M$ (celle × indizi) | Calcolo diretto via `game_model.clues` (predicati `And`/`Or`/`Not` valutati per tile), non materializzato come matrice |
| Vettore di conoscenza $V^p$ per giocatore | `HypothesisSpace` prodotto da `infer_hypothesis_space()` in [`ai/inference.py`](../ai/inference.py) — tiene traccia delle clue ancora compatibili per ciascun giocatore |
| `decideNextMove` / `findMostUnsurePlayer` / `findMostInformativeCell` | `recommend_moves()` in [`ai/strategy.py`](../ai/strategy.py) — scoring e ranking delle mosse candidate (ask vs claim) |
| `giveLessInformativeClue` / `isCellValid` | Gestite nel flusso di aggiornamento incrementale in [`ai/knowledge_update.py`](../ai/knowledge_update.py) a partire dagli eventi in [`ai/events.py`](../ai/events.py) |
| Orchestrazione turno/mossa | [`ai/engine.py`](../ai/engine.py) (non presente nello schizzo originale) |
| Valutazione su scenari reali/sintetici | [`ai/scenario_harness.py`](../ai/scenario_harness.py), vedi `docs/AI_SCENARIO_HARNESS.md` (non presente nello schizzo originale) |

Per il comportamento e le firme effettive, fare riferimento al codice in `ai/` e ai relativi test in `tests/`;
questo documento resta valido come motivazione concettuale ma non come specifica implementativa.

## Come funziona oggi, in dettaglio

L'algoritmo si divide in tre livelli: **inferenza** (cosa sappiamo), **strategia** (cosa conviene fare) e
**orchestrazione incrementale** (come si aggiorna lo stato turno per turno).

### 1. Inferenza: `infer_hypothesis_space()` — [`ai/inference.py`](../ai/inference.py)

Input: uno `GameSnapshot` (board + token round/cube osservati per ciascun giocatore) e il catalogo indizi
(`build_clue_catalog(include_inverse=...)` da [`game_model/clues.py`](../game_model/clues.py)).

Passi:

1. **Match indizio→tile.** Per ogni indizio del catalogo calcola l'insieme di tile che lo soddisfano
   (`clue.matches(tile, board)`). Gli indizi senza alcun tile compatibile su questa board vengono scartati
   (`clue_match_tiles`).
2. **Filtro locale per giocatore.** Per ciascun giocatore, un indizio resta "possibile" solo se:
   - nessuno dei suoi tile con **cube** (risposta "no") è nell'insieme di match dell'indizio (altrimenti
     l'indizio direbbe "sì" lì, contraddicendo l'osservazione);
   - tutti i suoi tile con **round** (risposta "sì") sono un sottoinsieme dell'insieme di match dell'indizio.
   Questo produce `local_possible_clue_ids_by_player`: gli indizi compatibili con le sole osservazioni
   *di quel giocatore*, indipendentemente dagli altri.
3. **Filtro globale (CSP con vincolo di unicità del covo).** Il punto più sofisticato dell'algoritmo:
   `_globally_feasible_clue_ids_by_player()` fa un **backtracking search** che assegna a ciascun giocatore
   uno dei suoi indizi localmente possibili, con due vincoli:
   - **indizi tutti diversi tra giocatori** (nel mazzo fisico ogni carta indizio è unica, nessun giocatore
     condivide l'indizio di un altro — vedi `test_infer_hypothesis_space_enforces_unique_clue_per_match`);
   - **l'intersezione dei tile-match di tutti gli indizi assegnati deve avere dimensione esattamente 1** —
     questo codifica l'invariante di gioco per cui esiste sempre *un solo* covo reale, valido simultaneamente
     per l'indizio segreto di ogni giocatore.
   Un indizio viene marcato come "globalmente fattibile" per un giocatore solo se esiste **almeno una**
   assegnazione completa e valida (per tutti i giocatori) in cui quel giocatore ha quell'indizio. I giocatori
   vengono ordinati per numero di candidati locali crescente (euristica "most-constrained-first", buona
   prassi nei CSP) e ogni ramo viene tagliato appena l'intersezione corrente si svuota o appena
   `_remaining_players_can_match()` rileva che un giocatore successivo non ha più nessun indizio compatibile
   con l'intersezione corrente.
4. **Output.** Per ciascun giocatore: `possible_clue_ids` (post-filtro globale), `candidate_tiles` (unione dei
   match dei suoi indizi possibili), `guaranteed_tiles` (intersezione — tile validi per *ogni* indizio ancora
   possibile), `eliminated_tiles`. A livello di board: `global_candidate_tiles()`/`global_guaranteed_tiles()`
   intersecano questi insiemi su tutti i giocatori (e, se noto, con l'indizio reale del bot).

### 2. Strategia: `recommend_moves()` — [`ai/strategy.py`](../ai/strategy.py)

1. Se non fornito, ricalcola l'hypothesis space (senza sapere l'indizio reale del bot, a meno che
   `bot_valid_tile_ids` non venga passato da `CryptidAIEngine`).
2. **Candidate "claim" (`ask_is`).** Per ogni tile nei `global_candidate_tiles` senza alcun cube e valido per
   l'indizio del bot: `score = 2.0 + 1.5 * round_count`, +`1.0` se il tile è anche in `global_guaranteed_tiles`.
   Sono pesi euristici fissi, non calibrati (vedi Criticità).
3. **Candidate "ask" (`ask_could`).** Per ogni giocatore non-bot non ancora risolto (`is_resolved` falso) e
   ogni tile non già segnato cube per lui: `_expected_clue_elimination_metrics()` calcola, assumendo
   **probabilità uniforme** su ciascun indizio ancora possibile per quel giocatore, quante clue verrebbero
   eliminate se risponde "sì" (`no_count`) o "no" (`yes_count`), pesate dalla rispettiva probabilità —
   il valore atteso di clue eliminate è il punteggio.
4. **Scelta del tipo di azione.** `_preferred_action_type()` decide UNA sola tipologia (`ask_is` oppure
   `ask_could`) per tutta la lista: se `1 / len(global_candidates) >= claim_threshold` (default `0.35`) o c'è
   un solo candidato, si preferisce `ask_is`; altrimenti `ask_could`. Le mosse dell'altro tipo vengono scartate
   dal risultato finale, anche se singolarmente avrebbero punteggio alto.
5. Le mosse superstiti sono ordinate per punteggio decrescente, le prime `top_k` vengono restituite con una
   confidenza via **softmax** dei punteggi (non una probabilità di vittoria vera e propria, solo una
   normalizzazione relativa tra le mosse proposte).

### 3. Orchestrazione: `CryptidAIEngine` — [`ai/engine.py`](../ai/engine.py) + [`ai/knowledge_update.py`](../ai/knowledge_update.py)

- `KnowledgeTracker` mantiene la lista di osservazioni (`ObservationRecord`) e ricostruisce da zero uno
  `GameSnapshot` + `HypothesisSpace` ad ogni chiamata (`rebuild_hypothesis_space`) — nessuno stato
  incrementale "vero", solo un log di eventi rigiocato.
- `next_move()` calcola `bot_valid_tile_ids` dal vero indizio del bot (`_bot_clue()`) e lo passa a
  `recommend_moves` per restringere i candidati "claim" a tile realmente validi per il bot.
- `answer_for_tile()` / `is_cell_valid_for_me()`: quando un avversario chiede "potrebbe essere qui?", il bot
  risponde in modo puramente deterministico confrontando il tile con il proprio indizio reale (`_matches_bot_clue`) —
  nessuna libertà strategica qui, la regola del gioco impone una risposta veritiera.
- `place_least_informative_cube()`: quando il bot stesso ha chiesto e ha ricevuto un "no", per regola deve
  piazzare un cube su un tile non valido per il proprio indizio. Tra tutti i tile non validi, sceglie quello
  che **minimizza l'informazione rivelata su di sé**: per ciascun candidato, simula la risposta "no" lì
  (`_snapshot_with_bot_observation`) e misura quanti indizi del bot verrebbero eliminati
  (`current_bot_space` vs `bot_space` simulato), scegliendo il tile con la riduzione minima.

## Criticità

### 1. ~~Blow-up combinatorio del solver CSP a inizio partita~~ — Risolto (soglia di tempo + fallback)

Il backtracking in `_globally_feasible_clue_ids_by_player()` è l'unico punto realmente sofisticato
dell'algoritmo, ma la sua euristica di pruning (`_remaining_players_can_match`) controlla solo, per ogni
giocatore rimanente **preso singolarmente**, se esiste *un* indizio compatibile con l'intersezione corrente —
non verifica la compatibilità *congiunta* dei giocatori rimanenti tra loro. Con pochi vincoli (poche
osservazioni), questo lascia esplorare rami che falliranno solo molti livelli più in profondità.

Misurato direttamente su questo repo (`data/board_loader.load_default_board()`, **zero osservazioni**,
ripetuto più volte per escludere rumore di sistema — una prima misura isolata su "4 giocatori" aveva
mostrato un valore anomalo di oltre 60s che non si è più riprodotto: il numero affidabile, confermato su
più run consecutivi, è quello in tabella):

| Giocatori | Indizi (`include_inverse`) | Tempo |
|---|---|---|
| 1–3 | 24 (`False`) | 15–28 ms |
| 4 | 24 (`False`) | ~183 ms |
| 4 | 48 (`True`, modalità avanzata) | ~3.8 s |
| 5 | 24 (`False`) | ~2.3 s |
| **5** | **48 (`True`, modalità avanzata)** | **> 20 s (in un run di verifica, oltre 90 s)** |

La soglia reale di degrado severo è **5 giocatori**, aggravata dalla modalità avanzata (48 indizi invece di
24, aggiunta lato UI nella stessa sessione di lavoro): il gioco supporta fino a 5 giocatori
(`GameSetupForm`), quindi il caso peggiore (5 giocatori + modalità avanzata + sessione appena creata) è
pienamente raggiungibile dall'app reale.

**Perché non era stato notato prima di misurarlo**: sia i test (`tests/test_inference.py`,
`tests/test_strategy.py`) sia `ai/scenario_harness.py`/`scripts/evaluate_ai_scenarios.py` popolano sempre
delle osservazioni sintetiche *prima* di chiamare `infer_hypothesis_space` — il caso "board appena
composta, nessun token piazzato" non era mai stato esercitato. È un percorso realmente raggiungibile
nell'app: il bottone "Recalculate AI" (e il debounce automatico `scheduleAiSync()` in `App.jsx`) chiamano
`/recalculate` anche a sessione appena creata, con 4-5 giocatori configurati e zero clue/token ancora
inseriti.

**Fix applicato**: `infer_hypothesis_space()` accetta ora `time_budget_seconds` (default
`DEFAULT_HYPOTHESIS_TIME_BUDGET_SECONDS = 1.5s`, comfortably sopra ogni caso legittimo misurato). Il
backtracking controlla una deadline (`time.monotonic()`) ad ogni chiamata ricorsiva; se superata, abortisce
e `infer_hypothesis_space` ricade su un algoritmo "buono non ottimo": usa `local_possible_clue_ids_by_player`
(il filtro per-giocatore basato solo sulle proprie osservazioni, senza il vincolo di consistenza
multi-giocatore) e imposta `HypothesisSpace.is_approximate = True`. In questa modalità, `recommend_moves()`
(`ai/strategy.py`) interroga un **solo** giocatore bersaglio — quello con più indizi ancora possibili
(il più incerto), a parità scelto per ordine di turno — invece di tutti i giocatori non risolti, riprendendo
l'euristica `findMostUnsurePlayer` dello schizzo di design originale.

*Solidità del fallback*: `possible_clue_ids` calcolato solo localmente è sempre un **soprainsieme** di
quello che il solver globale produrrebbe (il filtro globale può solo rimuovere indizi, mai aggiungerne).
Quindi `candidate_tiles` può solo essere uguale o più grande, e `guaranteed_tiles` uguale o più piccolo: il
fallback non inventa mai un tile "garantito" falso e non nasconde mai un vero candidato — può solo essere
meno sicuro di quanto lo sarebbe il solver ottimo.

*Visibilità*: `/recalculate` e `/ask-ai` restituiscono un campo `data.ai_mode` (`"optimal"` o
`"approximate"`, visibile direttamente nel JSON grezzo già mostrato in UI) e, quando approssimato, un
warning non bloccante `AI_HYPOTHESIS_APPROXIMATED`. `RecommendedMove`/`AIMove` portano lo stesso flag
(`is_approximate`) per chi consuma l'API a livello di singola mossa.

*Cosa NON risolve*: la cache per sessione (criticità #3, già presente) resta indipendente e compone
naturalmente — una `HypothesisSpace` in cache porta con sé qualunque valore di `is_approximate` avesse al
momento del calcolo. Il fallback riduce la qualità delle deduzioni multi-giocatore quando attivo (per
design, vedi sopra); non è stato invece toccato il costo di `place_least_informative_cube` nel caso normale
(non approssimato): quel metodo chiama `infer_hypothesis_space` una volta per ogni tile candidato non valido
per il bot (fino a ~100 su 108), e anche a soli 2 giocatori questo porta il singolo endpoint
`/ai-place-cube` a ~2-3s in test locali — non è un blocco, ma è un candidato naturale per un futuro
miglioramento (memoizzare/batchare quei calcoli), non incluso in questo fix.

### 2. ~~Ricalcolo ridondante in `place_least_informative_cube`~~ — Risolto

`_cube_information_score()` ricalcolava `infer_hypothesis_space(snapshot=snapshot, ...)` (lo stato **senza**
simulare la nuova osservazione) ad **ogni** chiamata — ma `place_least_informative_cube()` la chiama una
volta per ogni tile candidato non valido per il bot (potenzialmente decine su 108). Il calcolo "baseline" era
identico ad ogni iterazione: veniva ricalcolato N volte invece di una sola.

**Fix applicato**: `place_least_informative_cube()` calcola l'hypothesis space di baseline una sola volta
prima del ciclo sui tile candidati e la passa a `_cube_information_score()`, che non la ricalcola più
internamente. Comportamento invariato (stesso tile scelto, stesso punteggio — verificato da
`tests/test_ai_engine.py::test_engine_place_least_informative_cube_updates_own_model`).

### 3. ~~Nessuna cache/memoizzazione tra chiamate vicine~~ — Risolto

Ogni chiamata a `/recalculate` o `/ask-ai` (ramo non-bot) ricostruiva l'hypothesis space da zero anche se le
osservazioni non erano cambiate rispetto alla chiamata precedente. Con il debounce di 350ms lato frontend che
richiama `/recalculate` dopo ogni singola modifica della board, lo stesso calcolo costoso poteva essere
ripetuto molte volte in rapida successione per stati quasi identici.

**Fix applicato**: `SpaRecognitionApi` (`spa_recognition/backend/api.py`) mantiene una cache per sessione
(`_hypothesis_cache`, protetta da un `threading.Lock` visto che `http_server.py` condivide un'unica istanza
tra i thread del server) che memorizza l'ultimo `HypothesisSpace` calcolato insieme a un'**impronta di
contenuto** (`_hypothesis_space_fingerprint`) dei soli dati da cui dipende: tile della board, strutture,
token osservati, ordine di turno, bot player e `include_inverse_clues`. L'impronta è basata sul *contenuto*
(via `json.dumps(..., sort_keys=True)`), non sull'identità degli oggetti, per evitare il rischio (raro ma
reale) che CPython riusi un `id()` dopo un garbage collection. `post_recalculate` e `post_ask_ai` (ramo
non-bot) usano questa cache invece di chiamare `infer_hypothesis_space` direttamente.

Misurato (stessa board, stesso stato, due chiamate consecutive a `/recalculate`):

| Configurazione | 1ª chiamata (cache miss) | 2ª chiamata (cache hit) |
|---|---|---|
| 3 giocatori, 24 indizi | ~27 ms | ~1.6 ms |
| 3 giocatori, 48 indizi (modalità avanzata) | ~127 ms | ~4.4 ms |

Un cambiamento reale dello stato (es. un nuovo token osservato) invalida automaticamente la cache, perché
cambia l'impronta — verificato da
`tests/test_spa_recognition_api.py::test_spa_recalculate_reuses_cached_hypothesis_space`.

**Nota**: questo non risolve la criticità #1 (il blow-up combinatorio a inizio partita) — la prima chiamata
in uno stato mai visto prima resta soggetta allo stesso costo del solver CSP. La cache elimina solo le
richieste *ripetute* con lo stesso stato, che sono comunque il caso più frequente in pratica (debounce
automatico + click manuale, richieste multiple ravvicinate).

### 4. Costanti euristiche non calibrate

I pesi `2.0` / `1.5` / `1.0` in `_build_scored_moves` e `claim_threshold=0.35` in `recommend_moves` sono
scelti empiricamente, senza una motivazione probabilistica esplicita né una verifica di sensibilità (es. uno
sweep di `claim_threshold` sugli scenari in `data/ai_scenarios/` per misurarne l'effetto sul tasso di vittoria
simulato). Non ci sono test che verificano cosa succede a comportamenti/qualità delle raccomandazioni se questi
valori cambiano.

### 5. Assunzione di probabilità uniforme sugli indizi possibili

`_expected_clue_elimination_metrics` assume che, per un giocatore, ogni indizio ancora in `possible_clue_ids`
sia equiprobabile. In realtà il solver CSP del punto 1 già sa quali combinazioni sono globalmente coerenti:
alcuni indizi residui hanno molte più assegnazioni complete valide per gli *altri* giocatori rispetto ad altri,
quindi a rigore andrebbero pesati in proporzione (una vera distribuzione a posteriori), non trattati come
equiprobabili.

### 6. Nessun modello degli avversari

Il punteggio di `ask_could` ottimizza solo l'informazione che il bot stesso guadagna. Non tiene conto che la
domanda e la risposta sono pubbliche: ogni indizio che il bot elimina per sé lo elimina anche, alla vista, per
tutti gli altri giocatori/avversari che osservano la board. Un bot più "competitivo" potrebbe preferire domande
informative per sé ma poco informative per chi è più vicino a vincere.

### 7. Dati diagnostici calcolati ma mai mostrati in UI

`post_recalculate` serializza l'intero `HypothesisSpace` (incluso `is_contradictory`, `is_resolved`,
`candidate_tiles`, `guaranteed_tiles` per giocatore) e un `ui_payload` dedicato
(`global_candidate_tiles`, `global_guaranteed_tiles`, `top_move`) — ma `App.jsx` legge solo
`response.data.recommended_moves` (mostrato come JSON grezzo) e non tocca né `hypothesis_space` né
`ui_payload`. In particolare, `is_contradictory` (un giocatore le cui osservazioni non sono compatibili con
*nessun* indizio — quasi certamente un errore di inserimento) non viene mai segnalato all'utente.

### 8. Semantica della "modalità avanzata" da confermare

`clues.md` descrive gli indizi invertiti come una caratteristica del *mazzo* ("è possibile avere l'inverso di
tutti gli indizi sopra"), non necessariamente come 48 carte tra cui scegliere liberamente per ogni giocatore.
L'implementazione attuale (sia in `ai/` sia nella UI appena aggiunta) tratta le 48 varianti come un unico
catalogo scelto liberamente per ciascun giocatore, con il solo vincolo di non-duplicazione tra giocatori — non
è stato verificato se questo corrisponda all'intento originale (una carta fisica per indizio, orientata una
volta per tutta la partita) o se sia una scelta deliberata più permissiva. Andrebbe confermato prima di
considerarlo "corretto".

## Possibili miglioramenti

In corrispondenza delle criticità sopra, in ordine di impatto stimato:

1. ~~Sostituire il pruning debole con propagazione dei vincoli / aggiungere un budget di tempo con
   fallback~~ — **Fatto** (la parte "budget + fallback"), vedi criticità #1. La propagazione dei vincoli
   vera e propria (arc-consistency / forward-checking, per rendere anche il *solve ottimo* più veloce senza
   mai ricorrere al fallback) resta un miglioramento futuro non implementato.
2. ~~Calcolare una sola volta la baseline in `place_least_informative_cube`~~ — **Fatto**, vedi criticità #2.
3. ~~Cache per snapshot per `infer_hypothesis_space`~~ — **Fatto**, vedi criticità #3.
4. **Rendere i pesi euristici espliciti e testati.** Estrarli in costanti nominate con un commento sul
   razionale, e aggiungere uno sweep negli scenari di `data/ai_scenarios/` (via `scripts/evaluate_ai_scenarios.py`)
   per osservare l'effetto di `claim_threshold` e dei pesi sul tasso di vittoria simulato prima di modificarli.
5. **Pesare `_expected_clue_elimination_metrics` per numero di assegnazioni globali coerenti** invece che in
   modo uniforme, riusando l'output del backtracking (che già enumera le assegnazioni valide) per stimare una
   probabilità a posteriori più accurata.
6. **Aggiungere (anche solo come metrica informativa, non necessariamente per cambiare la scelta) quanta
   informazione una domanda rivela agli avversari**, così l'utente può scegliere consapevolmente tra "la mossa
   più informativa per me" e "la mossa che rivela meno agli altri".
7. **Mostrare in UI i dati già calcolati**: stato per giocatore (risolto/contraddittorio/candidati), e un
   avviso esplicito quando `is_contradictory` è vero per qualcuno, invece del solo elenco mosse in JSON grezzo.
8. **Confermare la semantica corretta della modalità avanzata** con la fonte delle regole (o con l'utente) e,
   se necessario, vincolare il catalogo a un orientamento fisso per indizio per partita invece di 48 varianti
   liberamente combinabili.

## Pseudo-codice per AI decision making (design originale):

`search(hex)` e `question(player, cell)` sono le due mosse possibili che l'AI può scegliere.

```java
void decideNextMove(DataStructure boardState) {
    if (boardState.validHex.size() == 1) {
        return search(validHex.getFirst());
    }
    // maybe add some condition to search anyway if we are very sure about a location
    Player mostUnsurePlayer = findMostUnsurePlayer(boardState);
    Cell mostInformativeCell = findMostInformativeCell(boardState, mostUnsurePlayer);
    return question(mostUnsurePlayer, mostInformativeCell);
}
```

## Funzioni chiave:

### `Player findMostUnsurePlayer(BoardState boardState)`
Questa funzione si baserà su una metrica calcolata sul numero di celle possibili
per un giocatore e le clue possibili per quel giocatore.
Un giocatore con ancora molte possibilità per entrambe è più "incerto" e quindi più interessante da interrogare.

### `Cell findMostInformativeCell(BoardState boardState, Player player)`
Questa funzione si baserà su una metrica di "informatività" per ogni cella.
Dovrà fare un calcolo di quante clue possono essere eliminate per
un giocatore se quel giocatore risponde "sì" o "no" alla domanda su quella cella.
E questi due valori saranno proporzionati alla probabilità che quel giocatore risponda si o no.

### `Cell giveLessInformativeClue(BoardState boardState, Player player)`
Quando si fa una domanda ad un giocatore, se questo risponde no, anche noi dobbiamo mettere un "no" su una cella.
Per questo motivo, dobbiamo anche calcolare quale cella è meno informativa per noi, 
in modo da minimizzare l'informazione che diamo agli avversari quando rispondiamo "no".

### `boolean isCellValid(BoardState boarState, Cell cell, Clue myClue)`
Questa funzione serve semplicemente per rispondere ad una domanda fatta da un avversario.
Dovrà verificare se la cella in questione è compatibile con la nostra clue attuale, 
e quindi se dobbiamo rispondere "sì" o "no" alla domanda.

## Struttura dati

* $N$: Il numero totale delle celle.
* $K$: Il numero totale di *tutti i possibili indizi* esistenti nel gioco (es. "È blu", "È rossa", "È quadrata", "Non è grande", ecc.).
* $P$: I giocatori.

### La Matrice Maestra (Celle vs Indizi)

Matrice fissa $M$ di dimensione $N \times K$ (Celle come righe, Indizi come colonne).
Questa matrice contiene solo **1 (Vero)** e **0 (Falso)**.

* $M_{i,j} = 1$ se la cella $i$ rispetta l'indizio $j$.
* $M_{i,j} = 0$ se la cella $i$ NON rispetta l'indizio $j$.

> **Nota bene:** Questa matrice è universale, non cambia mai durante la partita.

### Vettori di Conoscenza dei Giocatori

Per ogni giocatore $p$, tieni traccia di un vettore booleano $V^p$ lungo $K$ (pari al numero di indizi possibili).

* All'inizio del gioco, ogni giocatore può avere qualsiasi indizio, quindi il vettore è tutto a 1: $V^p = [1, 1, 1, \dots, 1]$.
* Il tuo obiettivo durante il gioco è far diventare **0** il maggior numero possibile di elementi in questo vettore, 
fino a quando non ne rimarrà solo uno a 1 (l'indizio segreto che quel giocatore possiede).
* Manteniamo anche un vettore per noi stessi (anche se sappiamo il nostro indizio), per poter calcolare cosa
possono dedurre gli avversari in base agli indizi sulla board.

### Come aggiornare le informazioni (Le Domande)

Quando chiedi al giocatore $p$ se la cella $c_i$ può essere quella giusta, lui guarda il suo indizio segreto e ti risponde "Sì" o "No".

* **Se risponde SÌ:** Significa che l'indizio segreto del giocatore *deve* essere uno di quelli che valgono 1 per la cella $c_i$.
  Prendi la riga $i$ della Matrice Maestra e fai un'operazione logica AND con il vettore del giocatore:

$$V^p_{nuovo} = V^p_{vecchio} \land M_{i,*}$$


* **Se risponde NO:** Significa che l'indizio segreto *deve* essere uno di quelli che valgono 0 per la cella $c_i$.
  Inverti la riga $i$ (trasforma gli 1 in 0 e i 0 in 1) e fai l'AND:

$$V^p_{nuovo} = V^p_{vecchio} \land (\lnot M_{i,*})$$

