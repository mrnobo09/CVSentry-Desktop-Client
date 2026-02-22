import asyncio
import json
import heapq
import time
from typing import List, Dict, Any
from utils.frame_cache import frame_cache
from utils.draw_utils import draw_detections

async def frame_aggregator(redis_manager, camera_ids: list):
    """
    Aggregates weapon detection results, draws annotations, and yields frames
    for the RTMP broadcaster.
    """
    streams = {f"weapon:{cam_id}": "$" for cam_id in camera_ids}

    BUFFER_SIZE = 2
    LOG_EVERY_N = 30   # Log every Nth frame to keep output clean
    frame_buffers: dict = {cam_id: [] for cam_id in camera_ids}

    fps_stats = {cam_id: {"count": 0, "start_time": time.time()} for cam_id in camera_ids}
    FPS_REPORT_INTERVAL = 10

    # Per-camera counters for logging
    pulled_counts: dict = {cam_id: 0 for cam_id in camera_ids}
    yielded_counts: dict = {cam_id: 0 for cam_id in camera_ids}

    print(f"[app/aggregator] 🟢 Started for cameras: {camera_ids} | buffer={BUFFER_SIZE}")
    loop = asyncio.get_running_loop()

    while True:
        try:
            # Blocking Redis Read (Offloaded to thread)
            # Use get_client() — .client is None until first call (lazy init)
            r = redis_manager.get_client()
            response = await asyncio.to_thread(
                r.xread,
                streams=streams,
                count=1,
                block=100
            )

            if not response:
                await asyncio.sleep(0.001)
                continue

            for stream_name_bytes, messages in response:
                stream_name = stream_name_bytes.decode('utf-8')
                camera_id = stream_name.split(":")[-1]

                for message_id, fields in messages:
                    streams[stream_name] = message_id 

                    # --- 1. Decode Metadata ---
                    frame_id_bytes = fields.get(b'frame_id')
                    try:
                        frame_id = int(frame_id_bytes.decode('utf-8')) if frame_id_bytes else -1
                    except ValueError:
                        continue

                    # Log periodic Redis pulls per camera
                    pulled_counts[camera_id] = pulled_counts.get(camera_id, 0) + 1
                    pull_n = pulled_counts[camera_id]
                    if pull_n % LOG_EVERY_N == 0:
                        print(f"[app/{camera_id}] 📨 Pulled {pull_n} result frames from Redis weapon stream")

                    det_bytes = fields.get(b'detections')
                    detections = json.loads(det_bytes.decode('utf-8')) if det_bytes else []
                    
                    threat_bytes = fields.get(b'has_threat')
                    has_threat = threat_bytes.decode('utf-8') == 'True' if threat_bytes else False
                    
                    count_bytes = fields.get(b'detections_count')
                    det_count = int(count_bytes.decode('utf-8')) if count_bytes else 0

                    # --- 2. Fetch Frame ---
                    raw_frame_bytes = frame_cache.get(camera_id, frame_id)
                    if raw_frame_bytes is None:
                        continue # Skip expired frames

                    # --- 3. Latency Optimization: Conditional & Threaded Drawing ---
                    if detections:
                        # Optimization 2: Offload CPU-heavy drawing to thread pool
                        # This prevents blocking the async loop
                        annotated_frame_bytes = await loop.run_in_executor(
                            None, 
                            draw_detections, 
                            raw_frame_bytes, 
                            detections
                        )
                    else:
                        # Optimization 3: Skip drawing entirely if no detections
                        # Decoding/Encoding JPEGs is expensive; avoid it if image hasn't changed.
                        annotated_frame_bytes = raw_frame_bytes

                    # --- 4. Build Result ---
                    frame_data = {
                        "camera_id": camera_id,
                        "message_id": message_id.decode('utf-8'),
                        "frame_id": frame_id,
                        "frame_bytes": annotated_frame_bytes, 
                        "detections": detections,
                        "detections_count": det_count,
                        "has_threat": has_threat
                    }

                    # --- 5. Sort & Yield ---
                    if camera_id in frame_buffers:
                        heapq.heappush(frame_buffers[camera_id], (frame_id, frame_data))

                        if len(frame_buffers[camera_id]) > BUFFER_SIZE:
                            _, sorted_frame = heapq.heappop(frame_buffers[camera_id])

                            # Log periodic frame yields per camera
                            yielded_counts[camera_id] = yielded_counts.get(camera_id, 0) + 1
                            yield_n = yielded_counts[camera_id]
                            if sorted_frame.get("has_threat"):
                                print(f"[app/{camera_id}] 🚨 Yielding THREAT frame to SRS | frame_id={sorted_frame['frame_id']}")
                            elif yield_n % LOG_EVERY_N == 0:
                                print(f"[app/{camera_id}] 🖼️  Yielded {yield_n} annotated frames to RTMP broadcaster")

                            yield sorted_frame

                            # --- 6. FPS Calculation ---
                            stats = fps_stats[camera_id]
                            stats["count"] += 1
                            if stats["count"] >= FPS_REPORT_INTERVAL:
                                elapsed = time.time() - stats["start_time"]
                                current_fps = stats["count"] / elapsed
                                print(f"📊 [{camera_id}] Output FPS: {current_fps:.2f}")
                                # Reset counter
                                stats["count"] = 0
                                stats["start_time"] = time.time()

        except asyncio.CancelledError:
            print("Aggregator task cancelled.")
            break
        except Exception as e:
            print(f"⚠️ Aggregator Error: {e}")
            await asyncio.sleep(1)