from fastapi import APIRouter, Depends
from services.onvif_handler import discover_cameras
from schemas.cameras import Cameras
from services.analyzer import AnalyzeCameraStreams
from services.rtmp_service import start_rtmp_broadcasting
from dependencies.auth import verify_token, verify_node_ownership
from routes.node_routes import notify_cameras_active, re_register_node
from pydantic import BaseModel
import asyncio

router = APIRouter()

active_rtmp_task = None

@router.get("/list")
async def list_cameras(payload=Depends(verify_token)):
    """Endpoint to list discovered ONVIF cameras. Requires valid JWT + node ownership."""
    await verify_node_ownership(payload)
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
    await verify_node_ownership(payload)
    global active_rtmp_task
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
    if active_rtmp_task and not active_rtmp_task.done():
        active_rtmp_task.cancel()
    active_rtmp_task = asyncio.create_task(start_rtmp_broadcasting(camera_ids))

    return {
        "status": "System started",
        "details": f"Analyzing and Streaming {len(camera_ids)} cameras.",
        "note": "Weapon detection picks up streams automatically via Redis discovery."
    }


class StopPayload(BaseModel):
    cameras: list[str]

@router.post("/stop")
async def stop_camera_analysis(payload: StopPayload, token=Depends(verify_token)):
    """Stops analysis for the provided cameras."""
    await verify_node_ownership(token)
    global active_rtmp_task
    from services.analyzer import global_av_handler

    for cid in payload.cameras:
        await global_av_handler.stop_pipeline(cid)
    
    if active_rtmp_task and not active_rtmp_task.done():
        active_rtmp_task.cancel()
        active_rtmp_task = None

    await notify_cameras_active([], reason="analysis stopped")

    return {"status": "Analysis stopped"}