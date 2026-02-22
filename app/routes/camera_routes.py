from fastapi import APIRouter, Depends
from services.onvif_handler import discover_cameras
from schemas.cameras import Cameras
from services.analyzer import AnalyzeCameraStreams
from services.rtmp_service import start_rtmp_broadcasting
from dependencies.auth import verify_token
from routes.node_routes import notify_cameras_active, re_register_node
import asyncio

router = APIRouter()


@router.get("/list")
async def list_cameras(payload=Depends(verify_token)):
    """Endpoint to list discovered ONVIF cameras. Requires valid JWT."""
    cameras = discover_cameras()
    return cameras


@router.post("/start")
async def start_camera_analysis(cameras: Cameras, payload=Depends(verify_token)):
    """
    Starts:
    1. Analysis Loop (Reads RTSP → Redis streams)
    2. RTMP Service (Reads Aggregator → FFmpeg → SRS)

    Two Django node updates are triggered automatically:
      - Immediately here (camera IDs are registered as starting)
      - On first real frame in CameraWorker (cameras confirmed live)

    Weapon detection starts automatically — it polls Redis for
    stream:*:weapon_group keys and self-activates.
    """
    cameras_dict = cameras.root
    camera_ids = list(cameras_dict.keys())

    # Step 0: Ensure the node exists in Django (idempotent re-registration).
    # Handles the case where the node was pruned between login and Start.
    await re_register_node()

    # Step 1: Tell Django which cameras are starting
    await notify_cameras_active(camera_ids, reason="analysis started")

    # Start RTSP ingestion (frames → Redis)
    asyncio.create_task(AnalyzeCameraStreams(cameras_dict))

    # Start RTMP broadcasting (aggregator → FFmpeg → SRS)
    print(f"🎥 Starting RTMP Service for {len(camera_ids)} cameras...")
    asyncio.create_task(start_rtmp_broadcasting(camera_ids))

    return {
        "status": "System started",
        "details": f"Analyzing and Streaming {len(camera_ids)} cameras.",
        "note": "Weapon detection picks up streams automatically via Redis discovery."
    }