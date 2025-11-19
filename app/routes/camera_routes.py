from fastapi import APIRouter,WebSocket,WebSocketDisconnect
from services.onvif_handler import discover_cameras
from schemas.cameras import Cameras
from services.analyzer import AnalyzeCameraStreams
from utils.redis_manager import redis_manager
from utils.jpeg_to_base64 import jpeg_bytes_to_base64
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

@router.websocket("/ws/{camera_id}")
async def camera_ws_endpoint(websocket: WebSocket, camera_id: str):
    """
    WebSocket endpoint to stream processed frames for a specific camera.
    Fetches from Redis -> Converts to Base64 -> Sends JSON.
    """
    await websocket.accept()
    print(f"🟢 WebSocket connection accepted for camera {camera_id}")

    last_id = "$" 

    try:
        while True:
            
            response = await asyncio.to_thread(
                redis_manager.fetch_frames,
                camera_id=camera_id,
                last_id=last_id,
                count=1,
                block=100 
            )

            if response:
                # response format: [[stream_key, [(message_id, {data})]]]
                _, messages = response[0]

                for message_id, data in messages:
                    # Update last_id so the next loop gets the next frame
                    last_id = message_id

                    # 2. Extract raw bytes (Redis keys are bytes because decode_responses=False)
                    frame_bytes = data.get(b'frame_data')

                    if frame_bytes:
                        # 3. Convert to Base64
                        # include_prefix=True adds "data:image/jpeg;base64,..."
                        b64_image = jpeg_bytes_to_base64(frame_bytes, include_prefix=True)

                        # 4. Send as JSON
                        payload = {
                            "camera_id": camera_id,
                            "image": b64_image
                        }
                        print(f"➡️ Sending frame for camera {camera_id} via WebSocket")
                        await websocket.send_json(payload)

            # Yield control briefly to allow handling other tasks/disconnects
            await asyncio.sleep(0.001)

    except WebSocketDisconnect:
        print(f"🔴 WebSocket disconnected for camera {camera_id}")
    except Exception as e:
        print(f"⚠️ WebSocket error for camera {camera_id}: {e}")
    finally:
        # print(f"🔒 WebSocket connection closed for camera {camera_id}")
        pass