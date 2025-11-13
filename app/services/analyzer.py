import asyncio
from avhandler import AVHandler
from app.schemas.cameras import Cameras

async def AnalyzeCameraStreams(cameras:Cameras):
    """Analyze camera streams asynchronously."""
    for camera_id, camera_info in cameras.root.items():
        rtsp_url = camera_info.rtsp_url
        ip_address = camera_info.ip_address

        av_manager = AVHandler()

        asyncio.create_task(CameraWorker(camera_id, rtsp_url, av_manager))


async def CameraWorker(camera_id:str,rtsp_url:str,avhandler:AVHandler):
    """Worker to handle individual camera stream analysis."""
    try:
        await avhandler.start_pipeline(camera_id, rtsp_url)

        while True:
            frame = avhandler.get_frame(camera_id)

            await asyncio.sleep(0.001)

    except Exception as e:
        print(f"Failed to start pipeline for camera {camera_id}: {e}")

    finally:
        if camera_id in avhandler.containers:
            await avhandler.stop_pipeline(camera_id)
            print(f"Stopped pipeline for camera {camera_id}")

        
    