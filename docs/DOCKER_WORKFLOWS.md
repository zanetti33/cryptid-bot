# Docker Workflows

Questo progetto supporta una modalita Docker-first: il solo prerequisito richiesto e Docker con Docker Compose.

## Profili disponibili

- `dev`: backend Python + frontend Vite (hot reload)
- `prod`: backend Python + frontend statico servito con nginx
- `test`: esecuzione test Python in container
- `train`: training CNN con tentativo CUDA e fallback CPU

## Script Linux consigliati

Gli script sono in `scripts/docker/`:

- `doctor.sh`: verifica prerequisiti Docker e compose
- `dev.sh`: avvio stack sviluppo
- `prod.sh`: avvio stack produzione locale
- `test.sh`: esecuzione test
- `train.sh`: training CUDA con fallback CPU

## Esempi rapidi

```bash
chmod +x scripts/docker/*.sh
./scripts/docker/doctor.sh
./scripts/docker/dev.sh
./scripts/docker/test.sh
./scripts/docker/train.sh --epochs 10 --batch-size 16
```

## Volumi condivisi host-container

I servizi montano queste directory host:

- `./data`
- `./datasets`
- `./models`
- `./screenshots`

Questo permette persistenza e collaborazione tra moduli senza dipendere da stato interno ai container.

