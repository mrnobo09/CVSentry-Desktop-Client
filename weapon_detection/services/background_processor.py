import asyncio
import numpy as np
import json
import uuid 
from typing import List, Dict
from services.analysis import FrameAnalyzer
from concurrent.futures import ProcessPoolExecutor
from utils.RedisManager import redis_manager 
from turbojpeg import TurboJPEG

jpeg = TurboJPEG()

ANALYZER = FrameAnalyzer(skip_frames=2)

active_monitors: Dict[str, dict] = {}
CPU_EXECUTOR = ProcessPoolExecutor(max_workers=4)

GROUP_SUFFIX = "weapon_group"
CONSUMER_ID = f"worker_{uuid.uuid4().hex[:8]}"

# Log every Nth frame to avoid console spam
LOG_EVERY_N_FRAMES = 30

async def fetch_frames_task(camera_id: str, queue: asyncio.Queue):
    """
    Fetches frames from Redis Input Stream for processing.
    """
    input_stream = f"stream:{camera_id}:{GROUP_SUFFIX}"
    await redis_manager.ensure_group(input_stream, GROUP_SUFFIX)
    print(f"[weapon/{camera_id}] 🟢 Fetch task started (consumer: {CONSUMER_ID})")

    frames_received = 0

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

                frame_bytes = fields.get(b'frame_data')
                frame_id_bytes = fields.get(b'frame_id')
                frame_id = frame_id_bytes.decode('utf-8') if frame_id_bytes else None

                if frame_bytes is None:
                    await redis_manager.ack_message(input_stream, GROUP_SUFFIX, [msg_id])
                    continue

                # Use TurboJPEG for faster decoding
                frame = jpeg.decode(frame_bytes)

                if frame is not None:
                    frames_received += 1
                    if frames_received % LOG_EVERY_N_FRAMES == 0:
                        print(f"[weapon/{camera_id}] 📥 Pulled {frames_received} frames from Redis (latest frame_id={frame_id})")

                    if queue.full():
                        try: queue.get_nowait()
                        except asyncio.QueueEmpty: pass

                    await queue.put((frame, frame_id, msg_id))

        except asyncio.CancelledError:
            print(f"[weapon/{camera_id}] 🛑 Fetch task stopped (total frames received: {frames_received}).")
            break
        except Exception as e:
            print(f"[weapon/{camera_id}] ❌ Fetch Error: {e}")
            await asyncio.sleep(1)


async def process_camera_task(camera_id: str, queue: asyncio.Queue):
    """
    Analyzes frames and pushes ONLY metadata (detections) to the result stream.
    """
    print(f"[weapon/{camera_id}] 🟢 Analysis task started.")
    loop = asyncio.get_running_loop()
    input_stream_name = f"stream:{camera_id}:{GROUP_SUFFIX}"

    frames_processed = 0
    clean_frames = 0

    while True:
        try:
            data_package = await queue.get()
            frame, frame_id, msg_id = data_package

            detections = await loop.run_in_executor(
                CPU_EXECUTOR,
                ANALYZER.analyze_frame,
                frame
            )

            if frame_id:
                frames_processed += 1
                det_count = len(detections)
                has_threat = bool(detections)

                if has_threat:
                    # Always log threats immediately
                    threat_labels = [d.get('class_name', '?') for d in detections]
                    print(f"[weapon/{camera_id}] 🚨 THREAT detected | frame={frame_id} | count={det_count} | labels={threat_labels}")
                    clean_frames = 0
                else:
                    clean_frames += 1
                    if clean_frames % LOG_EVERY_N_FRAMES == 0:
                        print(f"[weapon/{camera_id}] ✅ Processed {frames_processed} frames | last {clean_frames} clean (no detections)")

                payload = {
                    "frame_id": frame_id,
                    "detections": json.dumps(detections),
                    "detections_count": str(det_count),
                    "has_threat": str(has_threat),
                    "worker_id": CONSUMER_ID
                }

                await redis_manager.client.xadd(
                    name=f"weapon:{camera_id}",
                    fields=payload
                )
                await redis_manager.ack_message(input_stream_name, GROUP_SUFFIX, [msg_id])

            await asyncio.sleep(0)

        except asyncio.CancelledError:
            print(f"[weapon/{camera_id}] 🛑 Analysis task stopped (total processed: {frames_processed}).")
            break
        except Exception as e:
            print(f"[weapon/{camera_id}] ❌ Analysis Error: {e}")
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