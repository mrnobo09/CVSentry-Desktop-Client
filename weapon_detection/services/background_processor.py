import asyncio
import cv2
import numpy as np
import json
import uuid 
from typing import List, Dict
from services.analysis import FrameAnalyzer
from concurrent.futures import ThreadPoolExecutor
from utils.RedisManager import redis_manager 

ANALYZER = FrameAnalyzer(skip_frames=0)

active_monitors: Dict[str, dict] = {}
CPU_EXECUTOR = ThreadPoolExecutor(max_workers=4)

GROUP_SUFFIX = "weapon_group"
CONSUMER_ID = f"worker_{uuid.uuid4().hex[:8]}" 

async def fetch_frames_task(camera_id: str, queue: asyncio.Queue):
    """
    Fetches frames from Redis Input Stream for processing.
    """
    input_stream = f"stream:{camera_id}:{GROUP_SUFFIX}"
    
    # Ensure Consumer Group exists
    await redis_manager.ensure_group(input_stream, GROUP_SUFFIX)
    
    print(f"[{camera_id}] Fetch task started as Consumer: {CONSUMER_ID}")

    while True:
        try:
            msgs = await redis_manager.read_group_stream(
                stream_key=input_stream,
                group_name=GROUP_SUFFIX,
                consumer_name=CONSUMER_ID
            )
            
            if not msgs: 
                continue

            _, entries = msgs[0]
            for msg_id_bytes, fields in entries:
                msg_id = msg_id_bytes.decode('utf-8') if isinstance(msg_id_bytes, bytes) else msg_id_bytes
                
                # We still need to READ the frame to analyze it
                frame_bytes = fields.get(b'frame_data')
                frame_id_bytes = fields.get(b'frame_id')
                
                # Only frame_id is strictly needed for the output
                frame_id = frame_id_bytes.decode('utf-8') if frame_id_bytes else None

                if frame_bytes is None: 
                    # Ack bad message so it doesn't get stuck
                    await redis_manager.ack_message(input_stream, GROUP_SUFFIX, [msg_id])
                    continue

                np_arr = np.frombuffer(frame_bytes, np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                if frame is not None:
                    if queue.full():
                        try: queue.get_nowait()
                        except asyncio.QueueEmpty: pass
                
                    await queue.put((frame, frame_id, msg_id))

        except asyncio.CancelledError:
            print(f"[{camera_id}] Fetch task stopped.")
            break
        except Exception as e:
            print(f"[{camera_id}] Fetch Error: {e}")
            await asyncio.sleep(1)


async def process_camera_task(camera_id: str, queue: asyncio.Queue):
    """
    Analyzes frames and pushes ONLY metadata (detections) to the result stream.
    """
    print(f"[{camera_id}] Analysis task started.")
    loop = asyncio.get_running_loop()
    input_stream_name = f"stream:{camera_id}:{GROUP_SUFFIX}"

    while True:
        try:
            data_package = await queue.get()
            frame, frame_id, msg_id = data_package
            
            # Analyze frame (CPU intensive)
            # We ignore the returned 'frame' since we aren't sending it back
            detections = await loop.run_in_executor(
                CPU_EXECUTOR,
                ANALYZER.analyze_frame,
                frame
            )

            # --- OUTPUT LOGIC ---
            # Only proceed if we have valid data
            if frame_id:
                detections_json = json.dumps(detections)
                det_count = len(detections)
                
                # Prepare Metadata Payload (NO IMAGES)
                payload = {
                    "frame_id": frame_id,
                    "detections": detections_json,
                    "detections_count": str(det_count),
                    "has_threat": str(bool(detections)),
                    "worker_id": CONSUMER_ID
                }
                
                # Push ONLY metadata to the result stream
                # Using client.xadd directly to avoid any image-wrapper logic in push_frame
                await redis_manager.client.xadd(
                    name=f"weapon:{camera_id}",
                    fields=payload
                )

                # ACK input message
                await redis_manager.ack_message(input_stream_name, GROUP_SUFFIX, [msg_id])
            
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
        active_monitors[cam] = {"queue": q, "tasks": [t1, t2]}

async def stop_cameras(camera_ids: List[str]):
    for cam in camera_ids:
        if cam not in active_monitors: continue
        tasks = active_monitors[cam]["tasks"]
        for t in tasks: t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        del active_monitors[cam]

async def stop_all():
    await stop_cameras(list(active_monitors.keys()))