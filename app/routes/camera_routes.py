from fastapi import APIRouter,WebSocket,WebSocketDisconnect
from services.onvif_handler import discover_cameras
from schemas.cameras import Cameras
from services.analyzer import AnalyzeCameraStreams
from utils.redis_manager import redis_manager
from utils.jpeg_to_base64 import jpeg_bytes_to_base64
from services.frame_aggregator import frame_aggregator
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

            requests.post(
                "http://192.168.0.100:8001/start-monitoring", 
                json={"cameras": camera_ids}, 
                timeout=5
            )

            print("✅ Microservice triggered")
        except Exception as e:
            print(f"❌ Microservice failed: {e}")

    await asyncio.to_thread(call_microservice)

    return {"status": "Analysis started"}




@router.websocket("/ws/{camera_id}")
async def camera_ws_endpoint(websocket: WebSocket, camera_id: str):
    await websocket.accept()
    
    try:
    
        async for data in frame_aggregator(redis_manager, [camera_id]):
            
            frame_bytes = data['frame_bytes']
            
            b64_image = jpeg_bytes_to_base64(frame_bytes, include_prefix=True)
            
            payload = {
                "camera_id": data['camera_id'],
                "frame_id": data['frame_id'],
                "has_threat": data['has_threat'], 
                "detections": data['detections'],  
                "image": b64_image
            }
            
            await websocket.send_json(payload)
            
            # Optional: Control frame rate
            await asyncio.sleep(0.001)

    except WebSocketDisconnect:
        print(f"🔴 Disconnected: {camera_id}")
    except Exception as e:
        print(f"⚠️ Error: {e}")