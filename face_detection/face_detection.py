from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
import numpy as np
from utils.RedisManager import redis_manager
from services import background_processor
from services.analysis import face_app

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

    print("🔥 Warming up Face Detection models in memory...")
    
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    try:
        if face_app:
            face_app.get(dummy_frame)
        print("✅ Face Detection models warmed up successfully.")
    except Exception as e:
        print(f"⚠️ Face Detection model warmup failed: {e}")

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
    Legacy endpoint — face data is now managed via Qdrant.
    The local Qdrant is synced automatically by the orchestrator.
    This endpoint now returns the current Qdrant connection status.
    """
    from services.analysis import global_qdrant
    connected = global_qdrant is not None
    count = 0
    if connected:
        try:
            info = global_qdrant.get_collection(collection_name="faces")
            count = info.points_count
        except Exception:
            pass
    return {
        "status": "qdrant_connected" if connected else "qdrant_disconnected",
        "known_faces_count": count,
    }
