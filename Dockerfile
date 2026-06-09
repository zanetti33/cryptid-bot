# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim AS py-base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-core.txt ./
RUN pip install --no-cache-dir -r requirements-core.txt

FROM py-base AS py-dev
COPY requirements-ml.txt ./
RUN pip install --no-cache-dir -r requirements-ml.txt
COPY . .

# Default command for local development backend.
CMD ["python", "-c", "from spa_recognition.backend.http_server import run; run(host='0.0.0.0', port=8000)"]

FROM py-base AS py-test
COPY requirements-ml.txt ./
RUN pip install --no-cache-dir -r requirements-ml.txt
COPY . .
CMD ["python", "scripts/run_tests.py", "-q"]

FROM py-dev AS py-runtime
CMD ["python", "-c", "from spa_recognition.backend.http_server import run; run(host='0.0.0.0', port=8000)"]

FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04 AS py-cuda
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip python3-dev build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-ml.txt requirements-core.txt ./
RUN python3 -m pip install --no-cache-dir -r requirements-core.txt \
    && python3 -m pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cu124
COPY . .

CMD ["python3", "scripts/train_module_classifier.py", "--data-path", "datasets/map_recognition", "--output", "models/module_classifier.pt"]


