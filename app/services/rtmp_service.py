import asyncio
import os
from typing import List, Dict
from utils.redis_manager import redis_manager as rdb
from services.frame_aggregator import frame_aggregator
from utils.rtmp_streamer import RTMPStreamer

# Configuration
SRS_BASE_URL = os.getenv("SRS_BASE_URL", "rtmp://localhost/live")  # Change this if SRS is on another IP

# Keep track of active tasks so we don't start duplicate streams
_active_stream_tasks: Dict[str, asyncio.Task] = {}

async def start_rtmp_broadcasting(camera_ids: List[str]):
    """
    Consumes processed frames and pushes them to SRS via RTMP.
    """
    streamers: Dict[str, RTMPStreamer] = {}

    print(f"🚀 Initializing RTMP Broadcast for: {camera_ids}")

    # 1. Initialize one Streamer per Camera
    for cam_id in camera_ids:
        # URL format: rtmp://localhost/live/cam_01
        stream_url = f"{SRS_BASE_URL}/{cam_id}"
        
        # Adjust width/height if your cameras are 1920x1080
        streamers[cam_id] = RTMPStreamer(stream_url, width=1280, height=720)
        streamers[cam_id].start()

    try:
        # 2. Consume the Aggregator Loop
        # This yields: { 'camera_id': '...', 'frame_bytes': b'...', ... }
        async for data in frame_aggregator(rdb, camera_ids):
            
            target_cam = data['camera_id']
            frame_bytes = data['frame_bytes']

            # 3. Route frame to the correct streamer
            if target_cam in streamers:
                streamers[target_cam].write(frame_bytes)

    except asyncio.CancelledError:
        print("🛑 RTMP Service Cancelled.")
    except Exception as e:
        print(f"🔥 RTMP Service Error: {e}")
    finally:
        # 4. Cleanup on exit
        print("Cleaning up RTMP processes...")
        for s in streamers.values():
            s.stop()