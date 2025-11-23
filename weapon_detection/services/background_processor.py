import asyncio
import cv2
import numpy as np
import json
from typing import List, Dict
from services.analysis import FrameAnalyzer
from utils.RedisManager import redis_manager
from concurrent.futures import ThreadPoolExecutor

ANALYZER = FrameAnalyzer(skip_frames=0)

active_monitors: Dict[str, dict] = {}
CPU_EXECUTOR = ThreadPoolExecutor(max_workers=4)

GROUP_SUFFIX = "weapon_group"

async def fetch_frames_task(camera_id: str, queue: asyncio.Queue):
    input_stream = f"stream:{camera_id}:{GROUP_SUFFIX}"
    last_id = "$"
    print(f"[{camera_id}] Fetch task started.")

    while True:
        try:
            msgs = await redis_manager.read_stream(input_stream, last_id)
            # print(f"[{camera_id}] Fetched messages: {msgs}") 
            if not msgs: 
                continue

            _, entries = msgs[0]
            for msg_id, fields in entries:
                last_id = msg_id
                
                frame_bytes = fields.get(b'frame_data')
                
                frame_id_bytes = fields.get(b'frame_id')
                frame_id = frame_id_bytes.decode('utf-8') if frame_id_bytes else None

                if frame_bytes is None: continue

                np_arr = np.frombuffer(frame_bytes, np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                if frame is not None:
                    if queue.full():
                        try: queue.get_nowait()
                        except asyncio.QueueEmpty: pass
                
                    await queue.put((frame, frame_id))

        except asyncio.CancelledError:
            print(f"[{camera_id}] Fetch task stopped.")
            break
        except Exception as e:
            print(f"[{camera_id}] Fetch Error: {e}")
            await asyncio.sleep(1)


async def process_camera_task(camera_id: str, queue: asyncio.Queue):
    print(f"[{camera_id}] Analysis task started.")
    counter = 0
    loop = asyncio.get_running_loop()

    while True:
        try:

            data_package = await queue.get()
            frame, frame_id = data_package
            
            analyzed_frame, detections = await loop.run_in_executor(
                CPU_EXECUTOR,
                ANALYZER.analyze_frame,
                frame
            )

            detections_json = json.dumps(detections)
            
            if analyzed_frame is not None:
                # --- RESOLUTION CHECK ---
                height, width = analyzed_frame.shape[:2]
                if counter % 50 == 0:
                     print(f"[{camera_id}] 📏 Pushing Frame Resolution: {width}x{height}")

                ret, buffer = cv2.imencode('.jpg', analyzed_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                
                if ret:
                
                    meta = {
                        "detections": detections_json, 
                        "has_threat": bool(detections),
                        "frame_id": frame_id 
                    }
                    
                    await redis_manager.push_frame(f"weapon:{camera_id}", buffer.tobytes(), meta)
                    counter = counter + 1
            
            await asyncio.sleep(0)

        except asyncio.CancelledError:
            print(f"[{camera_id}] Analysis task stopped.")
            break
        except Exception as e:
            print(f"[{camera_id}] Analysis Error: {e}")
            await asyncio.sleep(1)



async def start_cameras(camera_ids: List[str]):
    
    for cam in camera_ids:
        if cam in active_monitors:
            print(f"Camera {cam} is already active. Skipping.")
            continue
            
        print(f"🚀 Booting up monitor for: {cam}")
        
        q = asyncio.Queue(maxsize=1)
        
        t1 = asyncio.create_task(fetch_frames_task(cam, q))
        t2 = asyncio.create_task(process_camera_task(cam, q))
        
        active_monitors[cam] = {
            "queue": q,
            "tasks": [t1, t2]
        }

async def stop_cameras(camera_ids: List[str]):
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
    all_cams = list(active_monitors.keys())
    await stop_cameras(all_cams)