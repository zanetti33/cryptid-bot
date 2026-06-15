# AI Scenario Harness

Questo harness serve per valutare l'intero pacchetto `ai/` partendo da scenari iniziali descritti in JSON.

## Obiettivo

Dato uno scenario reale o semi-reale:

- configurazione mappa
- elenco giocatori
- ordine di turno
- clue reali di ogni giocatore, inclusa l'AI

l'harness genera automaticamente un set sintetico di osservazioni (`round`/`cube`) coerenti con quelle clue, esegue l'AI e produce un report leggibile.

## File di esempio

Usa come riferimento:

- `data/ai_scenarios/sample_default_layout.json`

## Dove mettere i file JSON

Salva i file scenario in:

- `data/ai_scenarios/`

Per esempio:

- `data/ai_scenarios/partita-2026-06-15.json`
- `data/ai_scenarios/finale-4-giocatori.json`

In questo modo puoi lanciare anche più scenari insieme con un glob:

```bash
cd "C:/Users/lzanetti/IdeaProjects/cryptid-bot-2"
python scripts/evaluate_ai_scenarios.py data/ai_scenarios/*.json
```

## Formato scenario

```json
{
  "scenario_id": "my-game-01",
  "description": "Partita di test",
  "board": {
    "kind": "default_layout",
    "structures": [
      {"tile_id": 18, "structure_type": "standing_stone", "structure_color": "white"},
      {"tile_id": 24, "structure_type": "standing_stone", "structure_color": "green"},
      {"tile_id": 30, "structure_type": "standing_stone", "structure_color": "blue"},
      {"tile_id": 42, "structure_type": "abandoned_shack", "structure_color": "white"},
      {"tile_id": 65, "structure_type": "abandoned_shack", "structure_color": "green"},
      {"tile_id": 77, "structure_type": "abandoned_shack", "structure_color": "blue"}
    ]
  },
  "players": [
    {"player_id": "bot", "clue_id": "within_two_bear_territory"},
    {"player_id": "p1", "clue_id": "terrain_pair_forest_desert"},
    {"player_id": "p2", "clue_id": "terrain_pair_forest_water"}
  ],
  "turn_order": ["bot", "p1", "p2"],
  "bot_player_id": "bot",
  "include_inverse_clues": false,
  "simulation": {
    "seed": 17,
    "observation_count": 10,
    "include_bot_observations": false,
    "ensure_player_polarity_coverage": true
  },
  "evaluation": {
    "top_k": 5
  }
}
```

## Board supportate

### 1. `default_layout`
Usa la board standard caricata da `data/`.

```json
{
  "board": {
    "kind": "default_layout"
  }
}
```

#### Quando usare `default_layout`

Usa `default_layout` quando la partita reale è stata giocata sulla mappa standard del progetto, cioè quella definita nei file già presenti in `data/`.

È il formato consigliato per iniziare, perché richiede meno dati e riduce il rischio di errori.

#### Formato completo consigliato per `default_layout`

```json
{
  "scenario_id": "partita-amici-01",
  "description": "Partita reale a 4 giocatori sulla board standard.",
  "board": {
    "kind": "default_layout",
    "structures": [
      {"tile_id": 18, "structure_type": "standing_stone", "structure_color": "white"},
      {"tile_id": 24, "structure_type": "standing_stone", "structure_color": "green"},
      {"tile_id": 30, "structure_type": "standing_stone", "structure_color": "blue"},
      {"tile_id": 42, "structure_type": "abandoned_shack", "structure_color": "white"},
      {"tile_id": 65, "structure_type": "abandoned_shack", "structure_color": "green"},
      {"tile_id": 77, "structure_type": "abandoned_shack", "structure_color": "blue"}
    ]
  },
  "players": [
    {"player_id": "bot", "clue_id": "within_two_bear_territory"},
    {"player_id": "p1", "clue_id": "terrain_pair_forest_desert"},
    {"player_id": "p2", "clue_id": "terrain_pair_forest_water"},
    {"player_id": "p3", "clue_id": "terrain_pair_forest_swamp"}
  ],
  "turn_order": ["bot", "p1", "p2", "p3"],
  "bot_player_id": "bot",
  "include_inverse_clues": false,
  "simulation": {
    "seed": 17,
    "observation_count": 12,
    "include_bot_observations": false,
    "ensure_player_polarity_coverage": true
  },
  "evaluation": {
    "top_k": 5
  }
}
```

#### Significato dei campi principali

- `scenario_id`: identificatore univoco leggibile
- `description`: testo libero per ricordare il contesto della partita
- `board.kind`: per questo caso deve essere `default_layout`
- `board.structures`: configurazione esplicita delle strutture della partita
- `players`: elenco dei giocatori con la loro clue reale
- `turn_order`: ordine di turno completo
- `bot_player_id`: quale giocatore è controllato dall'AI
- `include_inverse_clues`: di norma `false`, a meno che tu voglia includere anche le clue negate
- `simulation.seed`: seed random ripetibile
- `simulation.observation_count`: quante osservazioni sintetiche generare
- `simulation.include_bot_observations`: se `true`, genera anche pseudo-risposte del bot
- `simulation.ensure_player_polarity_coverage`: prova a generare sia `yes` sia `no` per ogni giocatore quando possibile
- `evaluation.top_k`: quante mosse AI mostrare nel report

#### Come specificare `board.structures`

Hai due modi supportati:

1. **Per `tile_id`**

```json
{
  "tile_id": 34,
  "structure_type": "standing_stone",
  "structure_color": "blue"
}
```

2. **Per modulo + local_id**

```json
{
  "section_id": "D",
  "local_id": 2,
  "structure_type": "abandoned_shack",
  "structure_color": "blue"
}
```

Quando `board.structures` è presente, l'harness considera quella lista come la fonte di verità per le strutture e sostituisce la disposizione automatica.

### 2. `placements`
Permette di specificare i 6 moduli della board.

```json
{
  "board": {
    "kind": "placements",
    "include_structure_markers": false,
    "placements": [
      {"slot_id": 1, "section_id": "A", "orientation": "normal"}
    ],
    "structures": [
      {"section_id": "A", "local_id": 9, "structure_type": "standing_stone", "structure_color": "green"}
    ]
  }
}
```

#### Quando usare `placements`

Usa `placements` solo se vuoi descrivere esplicitamente la composizione dei moduli della board invece di appoggiarti al layout standard già presente nel progetto.

Se stai usando un layout personalizzato, conviene quasi sempre specificare anche `board.structures` nello stesso file scenario.

## Cosa produce il report

Per ogni scenario:

- riepilogo scenario
- osservazioni sintetiche generate
- stato inferito per i giocatori
- mosse raccomandate dall'AI
- confronto tra output AI e clue reali

## Esecuzione

```bash
cd "C:/Users/lzanetti/IdeaProjects/cryptid-bot-2"
python scripts/evaluate_ai_scenarios.py data/ai_scenarios/default_layout.json
```

Con override dei parametri:

```bash
cd "C:/Users/lzanetti/IdeaProjects/cryptid-bot-2"
python scripts/evaluate_ai_scenarios.py data/ai_scenarios/*.json --seed 99 --observations 14 --top-k 7
```

## Come useremo i tuoi casi reali

Quando mi fornirai una partita reale, mi basteranno:

- giocatori
- ordine di turno
- clue di ciascuno
- configurazione mappa

Da lì potrò:

1. creare il file scenario JSON
2. generare osservazioni coerenti con le clue
3. eseguire l'AI con seed ripetibili
4. aggiungere test automatici che fissano il comportamento atteso


