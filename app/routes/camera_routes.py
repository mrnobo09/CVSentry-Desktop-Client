from fastapi import APIRouter
from services.onvif_handler import discover_cameras
from schemas.cameras import Cameras
from services.analyzer import AnalyzeCameraStreams
import requests
import asyncio

router = APIRouter()

@router.get("/list")
async def list_cameras():
    """Endpoint to list discovered ONVIF cameras."""
    cameras = discover_cameras()
    return cameras

@router.post("/start")
async def start_camera_analysis(cameras: Cameras):
    cameras_dict = cameras.root
    camera_ids = list(cameras_dict.keys())
    
    asyncio.create_task(AnalyzeCameraStreams(cameras_dict))

    def call_microservice():
        try:
            requests.post(
                "http://localhost:8001/start-monitoring", 
                json={"cameras": camera_ids}, 
                timeout=5
            )
            print("✅ Microservice triggered")
        except Exception as e:
            print(f"❌ Microservice failed: {e}")

    await asyncio.to_thread(call_microservice)

    return {"status": "Analysis started"}
