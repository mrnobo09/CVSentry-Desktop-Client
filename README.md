<div align="center">
  <img src="./Images/CVSentryLogo.png" alt="CVSentry Logo" width="150"/>
  <h1>CVSentry Desktop Client</h1>
  
  <strong>Distributed, highly-scalable on-premise orchestration for edge surveillance processing.</strong>
</div>

---

## Table of Contents

- [Deep Dive: Architecture & Scalability](#deep-dive-architecture--scalability)
- [Project Architecture](#project-architecture)
- [System Requirements](#system-requirements)
- [Environment Configuration](#environment-configuration)
- [Setup Instructions (Docker)](#setup-instructions-docker)
- [Manual Worker Setup (Advanced LAN Scaling)](#manual-worker-setup-advanced-lan-scaling)
- [Cloud System Reference](#cloud-system-reference)
- [License](#license)

---

## Deep Dive: Architecture & Scalability

The magic of the CVSentry Desktop Client lies in its completely decoupled, distributed microservices architecture based on a **Pub/Sub Broker pattern**. 

1. **The Orchestrator (`app/`)**: Captures raw RTSP video streams from local cameras, encodes them to JPEGs, and publishes them to a central Redis stream. It never blocks on AI processing.
2. **The Workers (`weapon_detection/`, `face_detection/`)**: These are independent worker processes. They continuously listen to the Redis streams, pull frames, run their respective AI inference models (YOLO / InsightFace), and publish the structured JSON results back to Redis.
3. **Aggregation & Streaming**: The orchestrator matches the inference metadata back to the raw video frame and streams both the WebRTC video (via aiortc) and metadata (via WebRTC DataChannels) directly to local dashboards or the Cloud relay.

### Horizontal LAN Scaling
**This is the system's most powerful feature.** Because the workers only communicate via Redis, they do not need to run on the same physical machine as the main orchestrator. 

You can add distributed local workers on any hardware across the same Local Area Network (LAN). If you want to add more cameras, simply utilize redundant hardware (old laptops, secondary servers, Jetson Nanos) on the same network. By pointing their `.env` Redis configuration to the main PC hosting the orchestrator, they will instantly begin consuming frames and distributing the inference workload. This massively boosts inference throughput and system performance without touching the core code.

## Project Architecture

```text
CVSentry-Desktop-Client/
├── app/                        # Main Orchestrator (FastAPI) & Frontend UI
│   ├── .env                    # Main application environment variables
│   ├── ui/                     # Local React/Vite Dashboard
│   └── app.py                  # Entrypoint for WebRTC, RTSP, and Redis coordination
│
├── face_detection/             # InsightFace Face Detection Microservice
│   ├── .env                    # Worker environment config
│   └── face_detection.py       # FastAPI worker entrypoint
│
├── weapon_detection/           # YOLO Weapon and Pose Detection Microservice
│   ├── .env                    # Worker environment config
│   └── weapon_detection.py     # FastAPI worker entrypoint
│
└── docker-compose.yml          # Redis, orchestrator app, and Qdrant database
```

## System Requirements

This system performs best on Linux distributions (e.g., **Arch Linux**, **Debian/Ubuntu-based systems**). For Windows users, it is highly recommended to run this within **WSL 2** (Windows Subsystem for Linux).

### System Dependencies
To ensure ultra-fast frame decoding and video ingestion, you must install the following system-level dependencies before running the application:

**Debian/Ubuntu (apt):**
```bash
sudo apt update
sudo apt install build-essential ffmpeg libturbojpeg0-dev
```

**Arch Linux (pacman):**
```bash
sudo pacman -S base-devel ffmpeg libjpeg-turbo
```

## Environment Configuration

You must configure multiple `.env` files across the different services. 

### 1. `Redis/.env` & `users.acl`
Before starting the infrastructure, the Redis instance requires its own configuration for secure authentication. 
1. Navigate to the `Redis/` directory.
2. Configure your `Redis/.env` file (e.g., `REDIS_PASSWORD=...`).
3. Set up the `users.acl` file to match the credentials used by the orchestrator and workers.

### 2. `app/.env` (Main Orchestrator)
```env
DJANGO_URL=http://localhost:8000
NODE_PORT=8001
NODE_WEBRTC_PORT=8001
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_USERNAME=cvsentry
REDIS_PASSWORD=
QDRANT_URL=http://localhost:6335
SRS_API_USERNAME=cvsentry_srs
SRS_API_PASSWORD=
```

### 3. `weapon_detection/.env` (Worker)
```env
REDIS_HOST=redis  # Change to the main PC's LAN IP if running on a separate machine
REDIS_PORT=6379
REDIS_USERNAME=cvsentry
REDIS_PASSWORD=
WEAPON_PORT=8002
COMPOSE_PROFILES=cuda # cuda | cpu | openvino
```

### 4. `face_detection/.env` (Worker)
```env
REDIS_HOST=redis  # Change to the main PC's LAN IP if running on a separate machine
REDIS_PORT=6379
REDIS_USERNAME=cvsentry
REDIS_PASSWORD=
FACE_PORT=8003
QDRANT_URL=http://qdrant:6333 # Change to main PC's LAN IP if separate
COMPOSE_PROFILES=cuda # cuda | cpu | openvino
```

## Setup Instructions (Docker)

To run the main orchestrator (which spins up the `app` server, Redis, and Qdrant all at once):

1. Open your terminal in the root directory of the client repository:
   ```bash
   # Run in: CVSentry-Desktop-Client/ (root directory)
   docker compose up --build
   ```
   This single command will:
   - Build and start the FastAPI Orchestrator application (with host networking enabled).
   - Spin up the secure Redis container with the mapped configuration and ACLs.
   - Initialize the Qdrant vector database.

2. Start the Local Dashboard UI:
   Navigate to the UI folder and start the React/Vite development server:
   ```bash
   # Run in: CVSentry-Desktop-Client/app/ui/
   cd app/ui
   npm install
   npm run dev
   ```

## Manual Worker Setup (Advanced LAN Scaling)

If the provided Dockerfiles do not work for your hardware, or you want to easily scale by adding workers on different physical machines in your LAN, you can run the workers directly in a Python virtual environment.

1. Install **Python 3.11.2** (strictly recommended) and the required system dependencies (`ffmpeg`, `libturbojpeg0-dev`) on the target machine.
2. Clone the repository on the target machine.
3. Update the `.env` file in the worker directory (e.g., `weapon_detection/.env`), ensuring `REDIS_HOST` points to the LAN IP address of the main orchestrator machine.
4. Create your virtual environment and run the worker:

**Weapon Detection Worker:**
```bash
# Run in: CVSentry-Desktop-Client/weapon_detection/
cd weapon_detection
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn weapon_detection:app --host 0.0.0.0 --port 8002
```

**Face Detection Worker:**
```bash
# Run in: CVSentry-Desktop-Client/face_detection/
cd face_detection
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn face_detection:app --host 0.0.0.0 --port 8003
```
The workers will automatically discover the Redis streams over the network and begin processing workloads instantly.

## Cloud System Reference

This edge client integrates closely with the central cloud infrastructure. For the cloud repository that handles global state, WebRTC relaying, and historical threat recordings, see [CVSentry](https://github.com/mrnobo09/CVSentry).

## License

This project is open-source. Anyone is free to self-host, customize, and use it.
