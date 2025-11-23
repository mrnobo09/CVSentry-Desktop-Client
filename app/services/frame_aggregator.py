import asyncio
import json
import heapq
from typing import List, Dict, Any

async def frame_aggregator(redis_manager, camera_ids: List[str]):
    """
    Aggregates frames, decodes them, and yields them SORTED by frame_id
    using a sliding window buffer (Min-Heap).
    """
    
    # Setup state tracking for Redis
    streams = {f"weapon:{cam_id}": "$" for cam_id in camera_ids}

    # Setup Sorting Buffers (One heap per camera)
    frame_buffers: Dict[str, list] = {cam_id: [] for cam_id in camera_ids}
    BUFFER_SIZE = 5 

    print(f"🔄 Aggregator started for: {list(streams.keys())} with buffer size {BUFFER_SIZE}")

    while True:
        try:
            # Run blocking synchronous Redis call in a thread
            response = await asyncio.to_thread(
                redis_manager.client.xread,
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
                    streams[stream_name] = message_id # Update stream offset

                    # --- DECODING LOGIC ---
                    frame_bytes = fields.get(b'frame_data')
                    if not frame_bytes: continue 

                    # Frame ID (Bytes -> Int)
                    frame_id_bytes = fields.get(b'frame_id')
                    try:
                        frame_id = int(frame_id_bytes.decode('utf-8')) if frame_id_bytes else -1
                    except ValueError:
                        frame_id = -1

                    # Detections (Bytes -> JSON String -> List/Dict)
                    detections_bytes = fields.get(b'detections')
                    detections = []
                    if detections_bytes:
                        try:
                            detections = json.loads(detections_bytes.decode('utf-8'))
                        except (json.JSONDecodeError, TypeError):
                            detections = []

                    # Threat Flag (Bytes -> String -> Bool)
                    threat_bytes = fields.get(b'has_threat')
                    has_threat = threat_bytes.decode('utf-8') == 'True' if threat_bytes else False

                    # Detections Count (Bytes -> Int)
                    count_bytes = fields.get(b'detections_count')
                    det_count = int(count_bytes.decode('utf-8')) if count_bytes else 0

                    # Create the clean data object
                    frame_data = {
                        "camera_id": camera_id,
                        "message_id": message_id.decode('utf-8'),
                        "frame_id": frame_id,
                        "frame_bytes": frame_bytes,
                        "detections": detections,
                        "detections_count": det_count,
                        "has_threat": has_threat
                    }

                    # --- SORTING LOGIC ---
                    
                    if camera_id in frame_buffers:
                        # Push the frame onto the heap, sorted by frame_id
                        heapq.heappush(frame_buffers[camera_id], (frame_id, frame_data))

                        # Yield the smallest item when the buffer is full
                        if len(frame_buffers[camera_id]) > BUFFER_SIZE:
                            _, sorted_frame = heapq.heappop(frame_buffers[camera_id])
                            yield sorted_frame

        except asyncio.CancelledError:
            print("Aggregator task cancelled.")
            break
        except Exception as e:
            print(f"⚠️ Aggregator Error: {e}")
            await asyncio.sleep(1)