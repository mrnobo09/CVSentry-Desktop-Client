from fastapi import APIRouter
from services.onvif_handler import discover_cameras

router = APIRouter()

@router.get("/list")
async def list_cameras():
    """Endpoint to list discovered ONVIF cameras."""
    cameras = discover_cameras()
    return cameras
