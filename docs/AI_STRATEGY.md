# AI Strategy

## Pseudo-codice per AI decision making:

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

## `findMostUnsurePlayer`
Questa funzione si baserà su una metrica calcolata sul numero di celle possibili
per un giocatore e le clue possibili per quel giocatore.
Un giocatore con ancora molte possibilità per entrambe è più "incerto" e quindi più interessante da interrogare.

## `findMostInformativeCell`
Questa funzione si baserà su una metrica di "informatività" per ogni cella.
Dovrà fare un calcolo di quanti esagoni possibili e quante clue possono essere eliminate per
un giocatore se quel giocatore risponde "sì" o "no" alla domanda su quella cella.
E questi due valori saranno proporzionati alla probabilità che quel giocatore risponda si o no.

## Struttura dati

