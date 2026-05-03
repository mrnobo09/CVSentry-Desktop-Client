from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio

from utils.RedisManager import redis_manager
from services import background_processor

# -----------------------------------------------------------------------
# Pattern weapon_detection watches for.
# Main app writes to: stream:{camera_id}:weapon_group
# We extract camera_id from that key and auto-start monitoring.
# -----------------------------------------------------------------------
STREAM_PATTERN = "stream:*:weapon_group"
DISCOVERY_INTERVAL = 5   # seconds between Redis key scans

async def _auto_discover_loop():
    """
    Polls Redis every DISCOVERY_INTERVAL seconds for new camera streams
    (keys matching stream:*:weapon_group) and automatically starts
    processing for any that we haven't seen yet.

    This removes the need for the main app to call /start-monitoring.
    """
    print("🔍 Auto-discover loop started — scanning for camera streams...")
    while True:
        try:
            r = redis_manager.get_client()
            # Scan for all existing weapon_group stream keys
            keys = await r.keys(STREAM_PATTERN)
            for key_bytes in keys:
                key = key_bytes.decode("utf-8")
                # key format: stream:{camera_id}:weapon_group
                parts = key.split(":")
                if len(parts) == 3:
                    camera_id = parts[1]
                    if camera_id not in background_processor.active_monitors:
                        print(f"📡 Discovered new stream for camera: {camera_id} — starting monitoring")
                        await background_processor.start_cameras([camera_id])
        except Exception as e:
            print(f"⚠️ Auto-discover error: {e}")

        await asyncio.sleep(DISCOVERY_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("--- 🔫 Weapon Detection Service Starting ---")

    print("🔥 Warming up YOLO models in memory...")
    from services.analysis import weapon_model, pose_model, INFERENCE_DEVICE
    import numpy as np
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    try:
        weapon_model.predict(source=dummy_frame, verbose=False, device=INFERENCE_DEVICE)
        pose_model.predict(source=dummy_frame, verbose=False, device=INFERENCE_DEVICE)
        print("✅ YOLO models warmed up successfully.")
    except Exception as e:
        print(f"⚠️ YOLO model warmup failed: {e}")

    # Connect to Redis
    try:
        await redis_manager.connect()
    except Exception as e:
        print(f"🚨 Critical Error: Could not connect to Redis. {e}")

    # Start auto-discovery loop — no HTTP trigger needed
    discover_task = asyncio.create_task(_auto_discover_loop())

    yield  # ← Application runs here

    print("--- 🛑 Weapon Detection Service Stopping ---")

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
    title="CVSentry - Weapon Detection Microservice",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def read_root():
    return {
        "service": "Weapon Detection",
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