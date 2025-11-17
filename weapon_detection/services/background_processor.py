import asyncio
import cv2
import numpy as np
from typing import List, Dict
from services.analysis import FrameAnalyzer
from utils.RedisManager import redis_manager

ANALYZER = FrameAnalyzer(skip_frames=0)

active_monitors: Dict[str, dict] = {}


async def fetch_frames_task(camera_id: str, queue: asyncio.Queue):
    
    input_stream = f"stream:{camera_id}"
    last_id = "$"
    print(f"[{camera_id}] Fetch task started.")

    while True:
        try:
            # Read from Redis
            msgs = await redis_manager.read_stream(input_stream, last_id)
            if not msgs: 
                continue

            _, entries = msgs[0]
            for msg_id, fields in entries:
                last_id = msg_id
                frame_bytes = fields.get(b'frame_data')
                if frame_bytes is None: continue

                # Decode
                np_arr = np.frombuffer(frame_bytes, np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                if frame is not None:
                    # Push to internal queue
                    if queue.full():
                        try: queue.get_nowait()
                        except asyncio.QueueEmpty: pass
                    await queue.put(frame)

        except asyncio.CancelledError:
            print(f"[{camera_id}] Fetch task stopped.")
            break
        except Exception as e:
            print(f"[{camera_id}] Fetch Error: {e}")
            await asyncio.sleep(1)


async def process_camera_task(camera_id: str, queue: asyncio.Queue):
    print(f"[{camera_id}] Analysis task started.")
    counter = 0
    while True:
        try:
            # Get frame from internal queue
            frame = await queue.get()
            
            # Analyze
            analyzed_frame, detections = await ANALYZER.analyze_frame(frame)
            
            # Push Result
            if analyzed_frame is not None:
                ret, buffer = cv2.imencode('.jpg', analyzed_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if ret:
                    meta = {"detections": len(detections), "has_threat": bool(detections)}
                    await redis_manager.push_frame(f"processed:{camera_id}", buffer.tobytes(), meta)
                    counter = counter + 1
                    print(f'Frame processed and pushed to redis {counter}')
            
            # Yield for other tasks
            await asyncio.sleep(0)

        except asyncio.CancelledError:
            print(f"[{camera_id}] Analysis task stopped.")
            break
        except Exception as e:
            print(f"[{camera_id}] Analysis Error: {e}")
            await asyncio.sleep(1)

async def start_cameras(camera_ids: List[str]):
    """Starts monitoring for the requested cameras if not already running."""
    
    for cam in camera_ids:
        if cam in active_monitors:
            print(f"Camera {cam} is already active. Skipping.")
            continue
            
        print(f"🚀 Booting up monitor for: {cam}")
        
        # 1. Create specific queue for this camera
        q = asyncio.Queue(maxsize=1)
        
        # 2. Create Tasks
        t1 = asyncio.create_task(fetch_frames_task(cam, q))
        t2 = asyncio.create_task(process_camera_task(cam, q))
        
        # 3. Store State
        active_monitors[cam] = {
            "queue": q,
            "tasks": [t1, t2]
        }

async def stop_cameras(camera_ids: List[str]):
    """Stops monitoring for specific cameras."""
    for cam in camera_ids:
        if cam not in active_monitors:
            continue
            
        print(f"Stopping monitor for: {cam}")
        tasks = active_monitors[cam]["tasks"]
        
        for t in tasks:
            t.cancel()
        
        await asyncio.gather(*tasks, return_exceptions=True)
        del active_monitors[cam]

async def stop_all():
    """Stops all running monitors (Graceful Shutdown)."""
    all_cams = list(active_monitors.keys())
    await stop_cameras(all_cams)