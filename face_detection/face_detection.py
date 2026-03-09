from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio

from utils.RedisManager import redis_manager
from services import background_processor

# -----------------------------------------------------------------------
# Pattern face_detection watches for.
# Main app writes to: stream:{camera_id}:face_group
# We extract camera_id from that key and auto-start monitoring.
# -----------------------------------------------------------------------
STREAM_PATTERN = "stream:*:face_group"
DISCOVERY_INTERVAL = 5   # seconds between Redis key scans


async def _auto_discover_loop():
    """
    Polls Redis every DISCOVERY_INTERVAL seconds for new camera streams
    (keys matching stream:*:face_group) and automatically starts
    processing for any we haven't seen yet.

    No HTTP trigger needed — this mirrors weapon_detection's auto-discovery.
    """
    print("🔍 [face] Auto-discover loop started — scanning for camera streams...")
    while True:
        try:
            r = redis_manager.get_client()
            keys = await r.keys(STREAM_PATTERN)
            for key_bytes in keys:
                key = key_bytes.decode("utf-8")
                # key format: stream:{camera_id}:face_group
                parts = key.split(":")
                if len(parts) == 3:
                    camera_id = parts[1]
                    if camera_id not in background_processor.active_monitors:
                        print(f"📡 [face] Discovered new stream for camera: {camera_id} — starting monitoring")
                        await background_processor.start_cameras([camera_id])
        except Exception as e:
            print(f"⚠️ [face] Auto-discover error: {e}")

        await asyncio.sleep(DISCOVERY_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("--- 👤 Face Detection Service Starting ---")

    # Connect to Redis
    try:
        await redis_manager.connect()
    except Exception as e:
        print(f"🚨 Critical Error: Could not connect to Redis. {e}")

    # Start auto-discovery loop
    discover_task = asyncio.create_task(_auto_discover_loop())

    yield  # ← Application runs here

    print("--- 🛑 Face Detection Service Stopping ---")

    # Stop auto-discovery
    discover_task.cancel()
    try:
        await discover_task
    except asyncio.CancelledError:
        pass

    # Stop all camera monitors
    await background_processor.stop_all()

    # Close Redis
    await redis_manager.close()


app = FastAPI(
    title="CVSentry - Face Detection Microservice",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def read_root():
    return {
        "service": "Face Detection",
        "status": "online",
        "version": "1.0.0",
        "active_cameras": list(background_processor.active_monitors.keys()),
    }


@app.get("/status")
async def status():
    """Returns currently monitored cameras (discovery is automatic)."""
    return {
        "active_cameras": list(background_processor.active_monitors.keys()),
        "count": len(background_processor.active_monitors),
    }


@app.post("/reload-faces")
async def reload_faces():
    """
    Hot-reload the known faces database without restarting the service.
    Call this after adding new images to the faces/ directory.
    """
    from services.analysis import ANALYZER
    ANALYZER.reload_known_faces()
    return {
        "status": "reloaded",
        "known_identities": list(ANALYZER.known_embeddings.keys()),
        "count": len(ANALYZER.known_embeddings)
    }
