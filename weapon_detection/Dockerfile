ARG RUNTIME=cuda

# --- STAGE 0: Base Selection ---
# We use aliases to conditionally pick the right base image

# CUDA Base (NVIDIA)
FROM nvidia/cuda:12.8.0-runtime-ubuntu24.04 AS base-cuda
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    libgl1 \
    libglib2.0-0 \
    libturbojpeg0 \
    && rm -rf /var/lib/apt/lists/*
ENV TORCH_INDEX_URL="https://download.pytorch.org/whl/cu121"

# CPU / OpenVINO Base
FROM python:3.11-slim AS base-cpu
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libturbojpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
ENV TORCH_INDEX_URL="https://download.pytorch.org/whl/cpu"

# OpenVINO is the same as CPU but kept distinct for clarity if we add specific OpenVINO system libraries
FROM base-cpu AS base-openvino
ENV TORCH_INDEX_URL="https://download.pytorch.org/whl/cpu"


# --- STAGE 1: Final Image ---
FROM base-${RUNTIME}
WORKDIR /app/weapon_detection

# Create a virtual environment
# In slim/ubuntu images it's best to use venv instead of overriding system python
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install Python packages
COPY requirements.txt .
# Install PyTorch from the specific index URL determined by the stage alias
RUN pip install torch torchvision --index-url $TORCH_INDEX_URL
RUN pip install --no-cache-dir -r requirements.txt

# Create volume mount point for weights
RUN mkdir -p /app/weapon_detection/weights

WORKDIR /app
COPY weapon_detection/ ./weapon_detection/
COPY utils/ ./utils/
# Copy main requirements just in case things in utils expect something, but we try to be self contained

# Start the worker
CMD ["uvicorn", "weapon_detection.weapon_detection:app", "--host", "0.0.0.0", "--port", "8002"]
