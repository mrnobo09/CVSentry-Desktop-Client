ARG RUNTIME=cuda

# --- STAGE 0: Base Selection ---

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
ENV ONNX_PACKAGE="onnxruntime-gpu"

# CPU Base
FROM python:3.11-slim AS base-cpu
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libturbojpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
ENV ONNX_PACKAGE="onnxruntime"

# OpenVINO Base
FROM base-cpu AS base-openvino
ENV ONNX_PACKAGE="onnxruntime onnxruntime-openvino"


# --- STAGE 1: Final Image ---
FROM base-${RUNTIME}
WORKDIR /app/face_detection

# Create virtual env
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY requirements.txt .

# Install dependencies, swapping onnxruntime dynamically based on base environment variables
RUN pip install --no-cache-dir $ONNX_PACKAGE
RUN sed -i '/onnxruntime/d' requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Create volume mount point for faces
RUN mkdir -p /app/face_detection/faces

WORKDIR /app
COPY face_detection/ ./face_detection/
COPY utils/ ./utils/

# Start the worker
CMD ["uvicorn", "face_detection.face_detection:app", "--host", "0.0.0.0", "--port", "8003"]
