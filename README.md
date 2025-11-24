````md
# 👁️ CVSentry Desktop Client

**Distributed On-Premise CCTV AI Processing System**

The CVSentry Desktop Client is a scalable, local surveillance solution that leverages a microservices architecture. It orchestrates multiple AI models (Object, Face, and Action detection) using Redis as a high-throughput message broker.

All processing occurs locally on-premise, ensuring data privacy and low latency. The system is designed for horizontal scaling—simply add more workers to increase inference throughput.

---

## 🚀 Key Features

- **Distributed Architecture:** Microservices run independently and communicate via Redis.
- **Horizontal Scaling:** Add more worker processes to handle more camera streams without code changes.
- **Real-time Aggregation:** The main backend aggregates inference results from multiple services and streams them to the UI via WebSockets.
- **Modern Stack:** Python (FastAPI/Uvicorn), Node.js (React/Vite), and Redis.

---

## 🧠 Architecture & Data Flow

The system operates on a Pub/Sub & Worker pattern:

1. **Ingestion:** The Main App captures frames from camera sources.
2. **Distribution:** Frames are published to specific Redis channels/queues.
3. **Inference:** Independent Microservices (Weapon, Face, Action) pull frames from Redis, perform preprocessing and inference, and push the results back to Redis.
4. **Aggregation:** The Main App picks up the processed results, aggregates them, and broadcasts the final data to the React UI.

---

## ⚙️ Prerequisites

- Redis Server (Must be running locally)
- Python 3.9+
- Node.js 18+
- Virtual Environment Tool (venv, conda, or poetry)

---

## 📦 Installation

### 1. Setup Python Environment

Create a virtual environment and install the backend dependencies.

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
````

### 2. Setup Frontend Environment

Install the React UI dependencies.

```bash
cd app/ui
npm install
```

---

## 🏃‍♂️ Running the Services

You will need to run the following services in separate terminal instances.

### 1. Start Redis

Ensure your local Redis server is running.

```bash
redis-server
```

### 2. Run the Main App (Orchestrator)

This service manages camera streams, aggregates results, and handles WebSocket connections.

```bash
cd app
uvicorn app:app --host 0.0.0.0 --port 4100
```

### 3. Run the Microservices

You can run as many instances of these as your hardware allows.

**⚔️ Weapon Detection**

```bash
uvicorn weapon_detection:app --host 0.0.0.0 --port 8001
```

**👤 Face Detection**

```bash
uvicorn face_detection:app --host 0.0.0.0 --port 8002
```

**🏃 Action/Posture Detection**

```bash
uvicorn action_detection:app --host 0.0.0.0 --port 8003
```

### 4. Run the User Interface

Launch the React dashboard.

```bash
cd app/ui
npm run dev
```

---

## 📂 Project Structure

```
CVSentry-Desktop-Client/
├── app/                  # Main Backend Orchestrator
│   ├── ui/               # React + Vite Frontend Dashboard
│   ├── main.py           # Entry point for aggregation & routing
│   └── ...
├── weapon_detection/     # Microservice: YOLO object/weapon detection
├── face_detection/       # Microservice: Face recognition & identification
├── action_detection/     # Microservice: Pose estimation & behavior analysis
├── requirements.txt      # Python dependencies
└── README.md
```

---

## 🛠️ Roadmap & Status

| Feature               | Status    | Notes                                           |
| --------------------- | --------- | ----------------------------------------------- |
| Core Inference Engine | ✅ Done    | Weapon, Face, and Action detection operational. |
| Redis Worker System   | ✅ Done    | Distributed frame processing implemented.       |
| UI Dashboard          | ✅ Done    | Live streaming and result visualization.        |
| Authentication        | ⏳ Pending | User login and secure access control.           |
| Alert Module          | ⏳ Pending | Logic for triggering system-wide alerts.        |
| Auto-Scaling          | ⏳ Pending | Automated worker launcher scripts.              |

---

## 📄 License

Distributed under the MIT License.

---

## 📞 Support

For support, please open an issue or pull request on the GitHub repository.

```
```
