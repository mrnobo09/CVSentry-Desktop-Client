from fastapi import APIRouter, Depends
from services.onvif_handler import discover_cameras
from schemas.cameras import Cameras
from services.analyzer import AnalyzeCameraStreams
from services.stream_service import start_streaming, stop_streaming
from dependencies.auth import verify_token, verify_node_ownership
from routes.node_routes import notify_cameras_active, re_register_node
from pydantic import BaseModel
import asyncio

router = APIRouter()

active_stream_task = None


@router.get("/list")
async def list_cameras(payload=Depends(verify_token)):
    await verify_node_ownership(payload)
    cameras = discover_cameras()
    return cameras


@router.post("/start")
async def start_camera_analysis(cameras: Cameras, payload=Depends(verify_token)):
    await verify_node_ownership(payload)
    global active_stream_task
    cameras_dict = cameras.root
    camera_ids = list(cameras_dict.keys())

    await re_register_node()

    await notify_cameras_active(camera_ids, reason="analysis started")

    asyncio.create_task(AnalyzeCameraStreams(cameras_dict))

    print(f"🎥 Starting WebRTC streaming for {len(camera_ids)} cameras...")
    if active_stream_task and not active_stream_task.done():
        active_stream_task.cancel()
    active_stream_task = asyncio.create_task(start_streaming(camera_ids))

    return {
        "status": "System started",
        "details": f"Analyzing and streaming {len(camera_ids)} cameras.",
        "note": "AI workers pick up streams automatically via Redis discovery."
    }


class StopPayload(BaseModel):
    cameras: list[str]


@router.post("/stop")
async def stop_camera_analysis(payload: StopPayload, token=Depends(verify_token)):
    await verify_node_ownership(token)
    global active_stream_task
    from services.analyzer import global_av_handler

    for cid in payload.cameras:
        await global_av_handler.stop_pipeline(cid)

    await stop_streaming(payload.cameras)

    if active_stream_task and not active_stream_task.done():
        active_stream_task.cancel()
        active_stream_task = None

    await notify_cameras_active([], reason="analysis stopped")

    return {"status": "Analysis stopped"}
