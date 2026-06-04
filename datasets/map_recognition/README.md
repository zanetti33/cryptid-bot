# Dataset `map_recognition`

Questa cartella e' il punto unico in cui tenere **immagini** e **label** usati per il riconoscimento della board.

## Struttura

```text
datasets/map_recognition/
├── images/          # screenshot sorgente
├── labels/          # un file JSON per ogni immagine
├── manifest.json    # indice dei sample presenti
└── README.md
```

## Convenzione nomi

Per ogni immagine in `images/` deve esistere un label con lo stesso nome base in `labels/`.

Esempio:

- immagine: `images/image_easy.png`
- label: `labels/image_easy.json`

## Formato label

Ogni label e' un file JSON con questa struttura logica:

```json
{
  "schema_version": 1,
  "sample_id": "image_easy",
  "image_path": "datasets/map_recognition/images/image_easy.png",
  "image_size": {
    "width": 1800,
    "height": 1182
  },
  "annotation_status": "verified",
  "board_layout": {
    "placements": [
      {
        "slot_id": 1,
        "section_id": "C",
        "orientation": "normal"
      }
    ],
    "structure_markers": [
      {
        "section_id": "C",
        "local_id": 4,
        "structure_type": "standing_stone",
        "structure_color": "white"
      }
    ]
  },
  "tiles": [
    {
      "q": 0,
      "r": 0,
      "terrain": "mountain",
      "section_id": "C",
      "local_id": 1,
      "animal": null,
      "structure_type": null,
      "structure_color": null,
      "tokens": []
    }
  ],
  "notes": ""
}
```

## Campi richiesti

### Top-level

- `schema_version`: versione del formato label.
- `sample_id`: identificatore del sample, di solito uguale al nome file senza estensione.
- `image_path`: path relativo dell'immagine.
- `image_size.width`, `image_size.height`: dimensione reale dell'immagine.
- `annotation_status`: uno tra:
  - `provisional`: generato automaticamente, da verificare
  - `verified`: verificato manualmente
- `board_layout`: annotazioni di alto livello della board.
- `tiles`: annotazioni tile-by-tile.
- `notes`: testo libero opzionale.

### `board_layout.placements`

Devono esserci **6 elementi**, uno per slot della board:

- `slot_id`: intero da `1` a `6`
- `section_id`: una tra `A`, `B`, `C`, `D`, `E`, `F`
- `orientation`: `normal` oppure `flipped`

### `board_layout.structure_markers`

Un elemento per ogni struttura presente:

- `section_id`
- `local_id`: intero da `1` a `18`
- `structure_type`: `standing_stone` oppure `abandoned_shack`
- `structure_color`: `white`, `green`, `blue`

### `tiles`

Devono esserci **108 elementi**, uno per ogni esagono globale della board.

Campi di ogni tile:

- `q`, `r`: coordinate globali nella griglia 18x6 (in pratica 18 colonne x 6 righe)
- `terrain`: `forest`, `mountain`, `water`, `desert`, `swamp`
- `section_id`: modulo a cui appartiene la tile
- `local_id`: id locale del modulo, da `1` a `18`
- `animal`: `bear`, `cougar` oppure `null`
- `structure_type`: come sopra, oppure `null`
- `structure_color`: come sopra, oppure `null`
- `tokens`: lista di oggetti nel formato:
  - `player_id`: stringa libera (`"bot"`, `"p1"`, ecc.)
  - `token_type`: `cube` oppure `round`

Se non stai ancora annotando i token, usa semplicemente `[]`.

## Regole pratiche consigliate

1. Usa `annotation_status = "provisional"` per label generate da script.
2. Passa a `"verified"` solo dopo controllo manuale.
3. Mantieni `image_path` relativo al repository, cosi' i file restano portabili.
4. Non rinominare una immagine senza rinominare anche il relativo file label.
5. Se aggiungi nuovi campi, incrementa `schema_version` solo in caso di breaking change.

## Generazione dei label iniziali

Per generare label JSON per tutte le immagini presenti in `images/`:

```bash
cd "/c/Users/lzanetti/IdeaProjects/cryptid-bot"
py -3.12 scripts/generate_map_dataset_labels.py --overwrite
```

> I label generati automaticamente nel repository sono marcati come `provisional`, perche' derivano dal layout canonico corrente e vanno validati manualmente prima di usarli come ground truth.


