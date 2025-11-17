from fastapi import FastAPI, HTTPException, Body
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import List

# Import your internal services
from utils.RedisManager import redis_manager
from services import background_processor

# ---------------------------------------------------------
# 1. Request Models (Validation)
# ---------------------------------------------------------
class MonitorRequest(BaseModel):
    cameras: List[str]

# ---------------------------------------------------------
# 2. Lifespan Manager (Startup & Shutdown)
# ---------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles the startup and shutdown events of the microservice.
    """
    print("--- 🔫 Weapon Detection Service Starting ---")
    
    # A. Connect to Redis (Infrastructure)
    try:
        await redis_manager.connect()
    except Exception as e:
        print(f"🚨 Critical Error: Could not connect to Redis. {e}")
        # We don't exit here to allow the app to start and report health errors
    
    yield  # <--- The application runs here
    
    print("--- 🛑 Weapon Detection Service Stopping ---")
    
    # B. Stop all background tasks gracefully
    await background_processor.stop_all()
    
    # C. Close Redis Connection
    await redis_manager.close()

# ---------------------------------------------------------
# 3. App Definition
# ---------------------------------------------------------
app = FastAPI(
    title="CVSentry - Weapon Detection Microservice",
    version="1.0.0",
    lifespan=lifespan
)

# ---------------------------------------------------------
# 4. API Routes
# ---------------------------------------------------------

@app.get("/")
async def read_root():
    return {
        "service": "Weapon Detection",
        "status": "online",
        "version": "1.0.0"
    }

@app.post("/start-monitoring", status_code=200)
async def start_monitoring(request: MonitorRequest):
    """
    Dynamically starts detection tasks for the list of cameras provided.
    """
    if not request.cameras:
        raise HTTPException(status_code=400, detail="Camera list cannot be empty")

    print(f"📥 Received command to START: {request.cameras}")
    
    await background_processor.start_cameras(request.cameras)
    
    return {
        "message": "Monitoring started",
        "targets": request.cameras,
        "total_active": list(background_processor.active_monitors.keys())
    }

@app.post("/stop-monitoring", status_code=200)
async def stop_monitoring(request: MonitorRequest):
    """
    Stops detection tasks for specific cameras.
    """
    print(f"📥 Received command to STOP: {request.cameras}")
    
    await background_processor.stop_cameras(request.cameras)
    
    return {
        "message": "Monitoring stopped",
        "targets": request.cameras,
        "remaining_active": list(background_processor.active_monitors.keys())
    }

# ---------------------------------------------------------
# Optional: Debug Entry Point
# ---------------------------------------------------------
# if __name__ == "__main__":
#     import uvicorn
#     # Run with: python weapon_detection.py
#     uvicorn.run("weapon_detection:app", host="0.0.0.0", port=8000, reload=True)