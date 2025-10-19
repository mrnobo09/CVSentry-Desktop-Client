# CVSentry Desktop Client

**CVSentry Desktop Client** is a plug-and-play desktop application for local CCTV video processing, including object detection, face recognition, and action detection. The application preprocesses video locally to reduce bandwidth and server load, sending only processed metadata to the central CVSentry Dashboard.

---

## Features

- Real-time video preprocessing from local CCTV cameras
- Object detection, face recognition, and action detection
- Lightweight, modular FastAPI microservices
- Modern React frontend served via PyWebView
- Fully plug-and-play: single installer with no separate Python or Node.js installation required

---

## Architecture Overview

[CCTV Cameras / Video Input]
|
v
[Local FastAPI Microservices] <-- AI processing (object, face, action detection)
|
v
[PyWebView GUI] <-- React frontend
|
v
[CVSentry Dashboard] <-- central server receives processed metadata


- **Local Node:** Handles all AI processing, keeping your system scalable.
- **Electron-free GUI:** PyWebView serves the React frontend locally.
- **Central Server:** Optional, receives processed metadata for monitoring, alerts, and historical analysis.

---

## Usage

- The desktop client GUI allows you to monitor local cameras and see real-time AI detection results.
- Settings and preferences can be accessed from the top-right menu.
- Processed events are automatically sent to the CVSentry Dashboard (optional, configurable).

---

## Related Projects

- [CVSentry Dashboard](https://github.com/mrnobo09/CVSentry) – Central web dashboard for monitoring processed events and reports.

