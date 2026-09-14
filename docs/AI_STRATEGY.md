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

