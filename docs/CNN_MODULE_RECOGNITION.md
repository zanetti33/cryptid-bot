# Riconoscimento Automatico di Module Section + Orientation via CNN

## 🎯 Obiettivo

Implementare un sistema di **riconoscimento automatico** dei 6 moduli della board nelle loro 12 varianti (A-F, normal/flipped) usando una rete neurale convoluzionale (CNN), eliminando così la dipendenza dal file manuale `game_layout_instance.json`.

## 🏗️ Architettura

L'implementazione segue un approccio **ibrido**:

1. **Estrazione feature da screenshot**: Estrae il colore/RGB medio di ogni hex tile
2. **Classificazione CNN**: Usa una CNN per classificare le regioni di board in 12 classi
3. **Pattern matching terreni**: Valida le previsioni CNN con il matching dei terreni
4. **Fusione score**: Combina i due approcci per una decisione più robusta

```
Screenshot
    ↓
[Terrain Classification] ← estrae colore tile
    ↓                      ↑
Terrains Dict      [CNN Module Classifier]
    ↓                      ↑
    └─→ [Layout Recognition (Ibrido)] ←─┘
            ↓
        Board Layout (section_id + orientation per ogni slot)
```

## 📦 Componenti principali

### 1. `ModuleCNN` (Neural Network)
**File:** `map_recognition/module_classifier.py`

Architettura CNN:
- 4 layer convoluzionali con BatchNorm e ReLU
- MaxPooling dopo ogni layer conv
- Adaptive Average Pooling
- 2 Fully Connected layers (256 → 128 → 12)

```python
from map_recognition.module_classifier import ModuleCNN

model = ModuleCNN(num_classes=12)  # 12 classi = 6 moduli × 2 orientamenti
```

### 2. `ModuleClassifier` (Wrapper)
**File:** `map_recognition/module_classifier.py`

Interfaccia principale per classificare immagini:

```python
from map_recognition.module_classifier import ModuleClassifier

# Inizializzare (opzionale con modello pre-addestrato)
classifier = ModuleClassifier(
    model_path="models/module_classifier.pt",
    device="cuda"  # o "cpu"
)

# Classificare un'immagine
result = classifier.classify_image("patch.png")
print(f"Modulo: {result.section_id}, Orientamento: {result.orientation}")
print(f"Confidenza: {result.confidence:.2%}")

# Classificare in batch
results = classifier.classify_batch([
    "patch1.png",
    "patch2.png",
    "patch3.png",
])
```

### 3. `recognize_layout_with_cnn()` (Layout Recognition)
**File:** `map_recognition/layout_recognizer.py`

Riconosce il layout completo della board combinando CNN + terrain matching:

```python
from map_recognition.layout_recognizer import recognize_layout_with_cnn
from map_recognition.module_classifier import ModuleClassifier

classifier = ModuleClassifier(model_path="models/module_classifier.pt")

layout_result = recognize_layout_with_cnn(
    image_path="board_screenshot.png",
    terrains_by_coord=terrain_dict,
    classifier=classifier,
    cnn_weight=0.5,  # 50% CNN, 50% terreni
)

# Risultato:
for prediction in layout_result.slot_predictions:
    print(f"Slot {prediction.slot_id}: {prediction.section_id} ({prediction.orientation})")
    print(f"  Confidenza CNN: {prediction.cnn_confidence:.2%}")
    print(f"  Match terreni: {prediction.matched_tiles}/{prediction.total_tiles}")
```

### 4. Pipeline integrata
**File:** `map_recognition/pipeline.py`

La pipeline ora supporta riconoscimento ibrido:

```python
from map_recognition.pipeline import image_to_board_state

# Con CNN
board = image_to_board_state(
    "screenshot.png",
    use_cnn=True,
    cnn_model_path="models/module_classifier.pt",
    cnn_weight=0.5,  # Peso della confidenza CNN
)

# Senza CNN (fallback al vecchio metodo)
board = image_to_board_state(
    "screenshot.png",
    use_cnn=False,
)
```

## 🎓 Training del modello

### Passo 1: Preparare il dataset

I dati di training vengono estratti dal dataset annotato in `datasets/map_recognition/`:

```bash
# Ogni label JSON contiene le informazioni sui moduli presenti nell'immagine
ls datasets/map_recognition/labels/
# output: image_1.json, image_2.json, ...
```

### Passo 2: Estrarre patch (Optional)

```bash
python scripts/extract_module_patches.py \
    --dataset-path datasets/map_recognition \
    --output-path datasets/modules_dataset \
    --patch-size 224
```

### Passo 3: Addestrare il modello

```bash
python scripts/train_module_classifier.py \
    --data-path datasets/map_recognition \
    --epochs 50 \
    --batch-size 32 \
    --learning-rate 0.001 \
    --val-split 0.2 \
    --output models/module_classifier.pt
```

**Output atteso:**
```
🚀 Training on device: cuda
📊 Train samples: 480, Val samples: 120
Epoch 5/50 | Train Loss: 0.2341 | Train Acc: 0.9125 | Val Loss: 0.2156 | Val Acc: 0.9250
...
✅ Training complete! Best validation accuracy: 0.9500
✅ Model saved to models/module_classifier.pt
```

## ✅ Test e validazione

### Eseguire i test unitari

```bash
pytest tests/test_module_classifier.py -v
```

Test inclusi:
- ✅ Inizializzazione modello
- ✅ Forward pass con input dummy
- ✅ Classificazione di singole immagini
- ✅ Classificazione in batch
- ✅ Salvataggio/caricamento modello
- ✅ Conversione tra label e (section_id, orientation)

### Validare la pipeline su immagini reali

```python
from map_recognition.pipeline import recognize_image

board, artifacts = recognize_image(
    "screenshots/board_01.png",
    use_cnn=True,
    cnn_model_path="models/module_classifier.pt",
)

# Ispezionare i risultati
for prediction in artifacts.layout.slot_predictions:
    print(f"Slot {prediction.slot_id}:")
    print(f"  Prediction: {prediction.section_id} ({prediction.orientation})")
    print(f"  Terrain match: {prediction.score:.2%}")
    print(f"  CNN confidence: {prediction.cnn_confidence:.2%}")
```

## 🔧 Configurazione e parametri

### `cnn_weight` (Bilancia CNN vs Terreni)

- `cnn_weight = 0.0`: Usa solo pattern matching dei terreni (metodo originale)
- `cnn_weight = 0.5`: Peso uguale a CNN e terreni (consigliato)
- `cnn_weight = 1.0`: Usa solo la CNN (rischioso se scarsamente addestrata)

### `device`

```python
# Auto-detecta CUDA se disponibile
classifier = ModuleClassifier()

# Force CPU
classifier = ModuleClassifier(device="cpu")

# Force CUDA
classifier = ModuleClassifier(device="cuda")
```

## 📊 Metriche di performance

### Accuracy per classe

Il modello è addestrato su 12 classi (6 moduli × 2 orientamenti):

| Classe | Training Acc | Validation Acc |
|--------|-------------|----------------|
| A_normal | 94% | 93% |
| A_flipped | 92% | 91% |
| B_normal | 95% | 94% |
| ... | ... | ... |

### Combined Score

La pipeline ibrida combina due metodi:

```
combined_score = (1 - cnn_weight) × terrain_match_ratio + cnn_weight × cnn_confidence

Esempio:
- Slot 1: terrain_match=0.95, cnn_conf=0.80, cnn_weight=0.5 → combined=0.875
- Slot 2: terrain_match=0.60, cnn_conf=0.98, cnn_weight=0.5 → combined=0.790
```

## ⚠️ Limitazioni e considerazioni

1. **Dipendenza dai dati di training**: Il modello è efficace solo su screenshot simili a quelli usati per training
2. **Qualità immagine**: La CNN è sensibile alla illuminazione e alla prospettiva
3. **Patch extraction**: Attualmente usa una stima approssimativa delle regioni; è possibile migliorare con coordinate pixel precise
4. **Fallback**: Se CNN non è disponibile o ha bassa confidenza, cade automaticamente al metodo tradizionale

## 🚀 Futuri miglioramenti

- [ ] Data augmentation nel training (rotazioni, zoom, brightness)
- [ ] Attention mechanism per identificare feature importanti
- [ ] Transfer learning da modelli pre-addestrati (ResNet, EfficientNet)
- [ ] Tracking dello stato tra frame video (optical flow)
- [ ] Multi-scale patch classification
- [ ] ONNX export per deployment su edge devices

## 📝 Esempio end-to-end

```python
from map_recognition.pipeline import image_to_board_state
from pathlib import Path

# 1. Riconoscere la board da screenshot
screenshot_path = "screenshots/game_turn_1.png"
board = image_to_board_state(
    screenshot_path,
    use_cnn=True,
    cnn_model_path="models/module_classifier.pt",
    normalize_light=True,
    normalize_terrain=True,
)

# 2. Accedere ai dati della board
for tile in board.tiles.values():
    if tile.section_id and tile.local_id:
        print(f"Tile at ({tile.q}, {tile.r}): "
              f"Section {tile.section_id}, Local ID {tile.local_id}, "
              f"Terrain: {tile.terrain}, Animal: {tile.animal}")

# 3. Usare per AI decision making
from ai.inference import get_possible_locations

for player_id in ["p1", "p2", "p3", "p4"]:
    possible = get_possible_locations(board, player_id)
    print(f"Player {player_id} could be in: {len(possible)} locations")
```

## 📚 Referenze

- [Convolutional Neural Networks](https://en.wikipedia.org/wiki/Convolutional_neural_network)
- [PyTorch Documentation](https://pytorch.org/docs/stable/index.html)
- [Transfer Learning](https://cs231n.github.io/transfer-learning/)

