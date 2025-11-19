import asyncio
import cv2
import numpy as np
from typing import List, Dict
from services.analysis import FrameAnalyzer
from utils.RedisManager import redis_manager
from concurrent.futures import ThreadPoolExecutor

ANALYZER = FrameAnalyzer(skip_frames=0)

active_monitors: Dict[str, dict] = {}
CPU_EXECUTOR = ThreadPoolExecutor(max_workers=4)

async def fetch_frames_task(camera_id: str, queue: asyncio.Queue):
    
    input_stream = f"stream:{camera_id}"
    last_id = "$"
    print(f"[{camera_id}] Fetch task started.")

    while True:
        try:
            msgs = await redis_manager.read_stream(input_stream, last_id)
            if not msgs: 
                continue

            _, entries = msgs[0]
            for msg_id, fields in entries:
                last_id = msg_id
                frame_bytes = fields.get(b'frame_data')
                if frame_bytes is None: continue

                np_arr = np.frombuffer(frame_bytes, np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                if frame is not None:
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
    loop = asyncio.get_running_loop()

    while True:
        try:
            frame = await queue.get()
            
            analyzed_frame, detections = await loop.run_in_executor(
                CPU_EXECUTOR,
                ANALYZER.analyze_frame,
                frame
            )
            
            if analyzed_frame is not None:
                # --- RESOLUTION CHECK START ---
                height, width = analyzed_frame.shape[:2]
                # cv2.circle(analyzed_frame, (300, 300), 100, (0, 0, 255), -1)
                
                # We print this every 50 frames to avoid spamming the console too hard,
                # but enough to see if the resolution changes or is wrong.
                if counter % 50 == 0:
                     print(f"[{camera_id}] 📏 Pushing Frame Resolution: {width}x{height}")
                # --- RESOLUTION CHECK END ---

                ret, buffer = cv2.imencode('.jpg', analyzed_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                
                if ret:
                    meta = {"detections": len(detections), "has_threat": bool(detections)}
                    await redis_manager.push_frame(f"processed:{camera_id}", buffer.tobytes(), meta)
                    counter = counter + 1
                    # print(f'Frame processed and pushed to redis {counter}')
            
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