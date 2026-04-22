# Use slim Python 3.11 as we don't need GPU for orchestration
FROM python:3.11-slim

# Install system dependencies (ffmpeg for RTMP streaming, libturbojpeg for fast encode/decode)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libturbojpeg0 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# We mount the source code during dev, but for prod we'd copy it
COPY . .

# Run uvicorn on port 8001
CMD ["uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "8001"]
