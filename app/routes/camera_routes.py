from fastapi import APIRouter
from services.onvif_handler import discover_cameras
from schemas.cameras import Cameras

router = APIRouter()

@router.get("/list")
async def list_cameras():
    """Endpoint to list discovered ONVIF cameras."""
    cameras = discover_cameras()
    return cameras

@router.post("/start")
async def start_camera_analysis(cameras:Cameras):
    """Endpoint to start analysis on selected cameras."""
    cameras_dict = cameras.root
    print(cameras_dict)  # Example usage of the Camera schema
    
    return {"status": "Analysis started"}
